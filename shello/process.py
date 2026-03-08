"""Process execution and management."""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from collections.abc import Container
from enum import Enum
from io import BufferedIOBase, TextIOBase
from pathlib import Path
from threading import Thread
from typing import IO, TYPE_CHECKING, Any, AnyStr, BinaryIO, TextIO, cast

if TYPE_CHECKING:
    from typing import Self

from .decorators import run_once, with_callback
from .exceptions import InvalidArgument, InvalidOperation, ProcessError, TimeoutError, UnexpectedExitCodeError
from .helpers import check_fd
from .pipeline import Pipeline
from .types import FileDescriptorLike

logger = logging.getLogger(__name__)


DEVNULL = subprocess.DEVNULL
STDOUT = subprocess.STDOUT
PIPE = subprocess.PIPE

# Acceptable exit codes - range(256) represents any valid exit code
ANY_EXITCODE = range(256)


class ProcessState(Enum):
    """Process execution states with numeric values for easy comparison."""

    PENDING = 0  # Initial state, no resources allocated
    SPAWNING = 1  # Transitional state during fork()
    RUNNING = 2  # Process executing with PID
    TERMINATED = 3  # Process finished, cleaned up


class Process:
    """Represents a process that can be executed."""

    KILL_GRACE_PERIOD: float = 10.0

    def __init__(
        self,
        program: str,
        *args: str,
        stdin: AnyStr | FileDescriptorLike | Path | None = None,
        stdout: FileDescriptorLike | Path | None = None,
        stderr: FileDescriptorLike | Path | None = None,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
        ok_exitcodes: Container[int] | int = 0,
        text: bool = False,
        timeout: float | None = None,
        capture_stdout: bool = True,
        capture_stderr: bool = True,
        print_stdout: bool = False,
        print_stderr: bool = False,
        wait: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize a Process.

        Args:
            program: The program to execute
            *args: Command line arguments for program
            stdin: Input source (string, file-like object)
            stdout: Output destination (None, file, path, STDOUT, STDERR)
            stderr: Error output destination (None, file, path, STDOUT, STDERR)
            cwd: Working directory
            env: Environment variables
            check: Whether to raise exception on non-zero exit
            ok_exitcodes: Acceptable exit codes (default: 0, use ANY_EXITCODE for any) - can be int or container
            text: Whether to treat I/O as text
            timeout: Timeout in seconds for process execution
            capture_stdout: Whether to capture stdout for later retrieval (default: True)
            capture_stderr: Whether to capture stderr for later retrieval (default: True)
            print_stdout: Whether to print stdout to console during execution (default: False)
            print_stderr: Whether to print stderr to console during execution (default: False)
            wait: Whether to wait for process to complete before returning
            **kwargs: Additional arguments passed to subprocess
        """
        self.program = program
        self.args = list(args)
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.cwd = cwd
        self.env = env
        self.check = check
        self.ok_exitcodes = (ok_exitcodes,) if isinstance(ok_exitcodes, int) else ok_exitcodes
        self.text = text
        self.timeout = timeout
        self.capture_stdout = capture_stdout
        self.capture_stderr = capture_stderr
        self.print_stdout = print_stdout
        self.print_stderr = print_stderr
        self._wait = wait
        self.kwargs = kwargs

        # Runtime state
        self._process: subprocess.Popen | None = None
        self._stdout_data: str | bytes | None = None
        self._stderr_data: str | bytes | None = None
        self._threads: list[Thread] = []
        self._state: ProcessState = ProcessState.PENDING
        self.start_time: float | None = None
        self.end_time: float | None = None
        self._exception: Exception | None = None
        self._lock = threading.RLock()
        self._threads_done_event = threading.Event()
        self._threads_done_set: set[threading.Thread] = set()
        self._threads_done_lock = threading.Lock()
        self._threads_total = 4  # number of distinct threads

        # Resource management
        self._opened_handles: list[IO] = []

    def __or__(self, other: Process) -> Pipeline:
        """Support shell-style pipeline operator: cmd1 | cmd2.

        Args:
            other: Process to pipe stdout into

        Returns:
            Pipeline connecting this process to the other

        Notes:
            If `other` is not a Process instance, returns NotImplemented
            to allow Python to handle the operation with the reflected method.
        """
        if not isinstance(other, Process):
            return NotImplemented

        return Pipeline(self, other)

    def execute(self) -> Process:
        """Execute the process.

        Starts the subprocess and begins background monitoring threads.
        If wait=True, blocks until completion.

        Returns:
            Self for method chaining

        Raises:
            InvalidOperation: If process already executed
            ProcessError: If command not found or subprocess fails
            TimeoutError: If process times out during execution
        """
        if self.state is not ProcessState.PENDING:
            logger.error("%s: execute() called in invalid state (%s)", self.program, self.state)
            raise InvalidOperation("Process already executed")

        with self._lock:
            logger.debug("%s: starting execution", self.program)
            self.state = ProcessState.SPAWNING

        try:
            self._process = subprocess.Popen(
                [self.program] + self.args,
                stdin=self._get_stdin_handle(),
                stdout=self._get_stdout_handle(),
                stderr=self._get_stderr_handle(),
                cwd=self.cwd,
                env=self.env,
                text=self.text,
                **self.kwargs,
            )
            self.start_time = time.time()
            self.state = ProcessState.RUNNING
            logger.debug("%s: process started. PID: %s", self.program, self.pid)

        except FileNotFoundError as e:
            raise ProcessError(
                command=[self.program] + self.args,
                exit_code=127,
                message=f"Command not found: {self.program}",
            ) from e
        except subprocess.SubprocessError as e:
            raise ProcessError(
                command=[self.program] + self.args,
                exit_code=-1,
                message=f"Subprocess error: {e}",
            ) from e
        except InvalidArgument as e:
            raise ProcessError(command=[self.program] + self.args, exit_code=-1, message=str(e)) from e
        except Exception:
            raise
        finally:
            self._cleanup_resources()

        self._background_monitor()

        if self._wait:
            self.wait()

        self._check_exception()

        return self

    @run_once
    @with_callback(on_done=lambda self: self._task_done())
    def _write_stdin(self) -> None:
        """Write stdin data to the process in a background thread.

        Handles string/bytes stdin input and closes the stream when done.
        """
        if self._process is None:
            logger.warning("%s: cannot write stdin – process is not started", self.program)
            return

        if self._process.stdin is None:
            logger.debug("%s: stdin is not writable (stdin=None)", self.program)
            return

        if not isinstance(self.stdin, (str, bytes)):
            logger.debug("%s: no stdin data to write", self.program)
            return

        try:
            logger.debug("%s: writing stdin", self.program)

            self._process.stdin.write(self.stdin)
            self._process.stdin.flush()

        except BrokenPipeError:
            # Child exited early or closed stdin
            logger.debug("%s: broken pipe while writing stdin", self.program)

        except Exception:
            logger.exception("%s: error while writing stdin", self.program)
            self._exception = self._exception or Exception(f"{self.program}: failed to write stdin")

        finally:
            try:
                self._process.stdin.close()
            except Exception:
                pass

    @run_once
    @with_callback(on_done=lambda self: self._task_done())
    def _read_stdout(self):
        """Read stdout from the process in a background thread.

        Handles capturing and/or printing stdout based on configuration.
        This method runs in a separate thread and is decorated with @run_once.
        """
        if self._process is None:
            logger.warning("%s: cannot read stdout – process is not started", self.program)
            return
        if self._process.stdout is None:
            logger.debug("%s: stdout is not captured (stdout=None)", self.program)
            return

        logger.debug("%s: self.capture_stdout: %s, self.print_stdout: %s", self.program, self.capture_stdout, self.print_stdout)

        if self.capture_stdout and self.print_stdout:
            stdout_chunks = []
            for line in self._process.stdout:
                stdout_chunks.append(line)
                print(f"{self.program} [stdout]: {line}", end="")
            self._stdout_data = "".join(stdout_chunks)

        elif self.capture_stdout:
            self._stdout_data = self._process.stdout.read()

        elif self.print_stdout:
            for line in self._process.stdout:
                print(f"{self.program} [stdout]: {line}", end="")

    @run_once
    @with_callback(on_done=lambda self: self._task_done())
    def _read_stderr(self):
        """Read stderr from the process in a background thread.

        Handles capturing and/or printing stderr based on configuration.
        This method runs in a separate thread and is decorated with @run_once.
        """
        if self._process is None:
            logger.warning("%s: cannot read stderr – process is not started", self.program)
            return
        if self._process.stderr is None:
            logger.debug("%s: stderr is not captured (stderr=None)", self.program)
            return

        if self.capture_stderr and self.print_stderr:
            stderr_chunks = []
            for line in self._process.stderr:
                stderr_chunks.append(line)
                print(f"{self.program} [stderr]: {line}", end="")
            self._stderr_data = "".join(stderr_chunks)

        elif self.capture_stderr:
            self._stderr_data = self._process.stderr.read()

        elif self.print_stderr:
            for line in self._process.stderr:
                print(f"{self.program} [stderr]: {line}", end="")

    @run_once
    @with_callback(on_done=lambda self: self._task_done())
    def _handle_execution(self) -> None:
        """Handle process execution and timeout monitoring in a background thread.

        Waits for the process to complete, handling timeouts and cleanup.
        """
        if self._process is None:
            logger.warning("%s: cannot wait – process is not started", self.program)
            return

        if not self.start_time:
            raise InvalidOperation("Process started without start_time")

        if self.timeout is not None:
            timeout = max(0, self.timeout - (time.time() - self.start_time))
        else:
            timeout = None
            logger.debug("%s: no timeout configured", self.program)

        try:
            logger.debug("%s: waiting for process to exit", self.program)
            self._process.wait(timeout=timeout)
            self.end_time = time.time()
            # Do not access self.returncode here: it raises an error
            # if the process has not been marked as terminated yet.
            logger.debug("%s: process exited with return code %s", self.program, self._process.returncode)
        except subprocess.TimeoutExpired:
            logger.warning("%s: timeout expired after %.2f seconds", self.program, self.timeout)
            self._process.kill()
            try:
                self._process.wait(self.KILL_GRACE_PERIOD)
            except subprocess.TimeoutExpired as e:
                raise Exception(f"{self.program}: process did not exit after kill") from e
            self._exception = TimeoutError("%s: process timed out after %.2f seconds", self.program, self.timeout)
        except Exception as e:
            logger.exception("%s: unexpected error in background monitor", self.program)
            self._exception = e
            if self._process.poll() is None:
                raise
        finally:
            if self._process.poll() is None:
                self._process.kill()
            if self.end_time is None:
                self.end_time = time.time()

    def _background_monitor(self) -> None:
        """Handle I/O collection and monitoring in background."""
        if self._process is None:
            raise InvalidOperation("Process not started")
        if self.is_done:
            logger.debug("%s: background monitor skipped (already done)", self.program)
            return

        logger.debug("%s: starting background monitor threads", self.program)

        self._threads.append(Thread(target=self._write_stdin, name=f"[{self.program} stdin]"))
        self._threads.append(Thread(target=self._read_stdout, name=f"[{self.program} stdout]"))
        self._threads.append(Thread(target=self._read_stderr, name=f"[{self.program} stderr]"))
        self._threads.append(Thread(target=self._handle_execution, name=f"[{self.program} wait]"))

        for thread in self._threads:
            thread.start()

    def _task_done(self) -> None:
        """Called when a background thread finishes.

        Tracks completion of background threads and marks the process as terminated
        when all threads have finished. This method is thread-safe and validates
        that each thread calls it exactly once.
        """
        thread = threading.current_thread()
        thread_name = thread.name
        thread_id = thread.ident
        with self._threads_done_lock:
            if thread_id in self._threads_done_set:
                # Thread should be done once
                raise RuntimeError(
                    f"{self.program}: _task_done() called more than once "
                    f"from the same thread "
                    f"(name={thread_name!r}, id={thread_id}). "
                    "This indicates a bug in thread lifecycle handling."
                )

            self._threads_done_set.add(thread)
            logger.debug("%s: thread done (%d/%d)", self.program, len(self._threads_done_set), self._threads_total)

            if len(self._threads_done_set) == self._threads_total:
                # Only when all distinct threads have finished
                logger.debug("%s: all threads done, setting process as TERMINATED", self.program)
                self.state = ProcessState.TERMINATED
                self._threads_done_event.set()

    @property
    def state(self) -> ProcessState:
        """Get current process state."""
        return self._state

    @state.setter
    def state(self, new_state: ProcessState) -> None:
        """Thread-safe state transition."""
        logger.debug("%s: process state change: %s -> %s", self.program, self.state, new_state)
        with self._lock:
            if self.state == new_state:
                raise InvalidOperation(f"Process already in state {new_state}")
            if self.state.value > new_state.value:
                raise InvalidOperation(f"Invalid state transition from {self.state} to {new_state}")

            self._state = new_state

    def _cleanup_resources(self) -> None:
        """Close all opened file handles."""
        for handle in self._opened_handles:
            try:
                if not handle.closed:
                    handle.close()
            except Exception:
                pass  # Ignore cleanup errors
        self._opened_handles.clear()

    def __del__(self) -> None:
        """Cleanup when object is garbage collected."""
        self._cleanup_resources()

    def wait(self) -> Self:
        """Wait for process completion and return exit code.

        Blocks until all background threads complete and process terminates.
        If check=True, validates exit code and raises exceptions.

        Returns:
            Self for method chaining

        Raises:
            InvalidOperation: If process not started
            UnexpectedExitCodeError: If exit code not in ok_exitcodes (when check=True)
        """
        if self._process is None:
            logger.error("%s: wait() called but process not started", self.program)
            raise InvalidOperation("Process not started")

        if self._threads_done_event.is_set():
            logger.debug("%s: wait() skipped – process already terminated", self.program)
            return self

        logger.debug("%s: waiting for all threads to finish", self.program)
        self._threads_done_event.wait()
        logger.debug("%s: background monitoring completed (state=%s)", self.program, self.state)

        if self.check:
            self.check_returncode()
            self._check_exception()
        return self

    def check_returncode(self) -> None:
        """Check if the process exit code is acceptable.

        Raises:
            UnexpectedExitCodeError: If the return code is not in ok_exitcodes.
        """
        if self.returncode not in self.ok_exitcodes:
            logger.warning(
                "%s: program exited unexpectedly with code %s (expected %s).",
                self.program,
                self.returncode,
                self.ok_exitcodes,
            )
            raise UnexpectedExitCodeError(
                f"{self.program}: program exited with code {self.returncode}, expected {self.ok_exitcodes}"
            )

    def _check_exception(self) -> None:
        """Raise stored exception if any.

        This method is called after process execution to raise any exceptions
        that occurred during background processing. The exception is cleared
        after being raised to prevent double-raising.
        """
        if self._exception:
            exc = self._exception
            self._exception = None  # Raise only once
            raise exc

    def kill(self, signal: int = 15) -> None:
        """Send signal to the process.

        Args:
            signal: Signal number to send (default: 15, SIGTERM)

        Raises:
            InvalidOperation: If process is not in a running state or not available
        """
        with self._lock:
            if self.state not in {ProcessState.RUNNING, ProcessState.SPAWNING}:
                raise InvalidOperation("Process not executed")

            if self._process is None or self._process.pid is None:
                raise InvalidOperation("Process not available for killing")

            self._process.send_signal(signal)

    @property
    def is_started(self) -> bool:
        """Check if process has started."""
        return self.state is not ProcessState.PENDING

    @property
    def is_done(self) -> bool:
        """Check if process has terminated."""
        return self.state == ProcessState.TERMINATED

    @property
    def pid(self) -> int | None:
        """Get process ID."""
        return self._process.pid if self._process else None

    @property
    def returncode(self) -> int:
        """Get process return code."""
        if self.state is not ProcessState.TERMINATED:
            raise InvalidOperation("Process not executed")
        return self._process.returncode if self._process else -1

    @property
    def stdout_data(self) -> str | bytes:
        """Get captured stdout."""
        if self.state is not ProcessState.TERMINATED:
            raise InvalidOperation("Process not executed")
        # self._check_exception()
        return self._stdout_data or ""

    @property
    def stderr_data(self) -> str | bytes:
        """Get captured stderr."""
        if self.state is not ProcessState.TERMINATED:
            raise InvalidOperation("Process not executed")
        # self._check_exception()

        return self._stderr_data or ""

    @property
    def execution_time(self) -> float | None:
        """Get total execution time from start to end."""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return None

    def __str__(self) -> str:
        """String representation of the command."""
        # Build base command
        cmd_parts = [self.program] + self.args
        cmd_str = " ".join(cmd_parts)

        # Add I/O redirections
        redirects = []

        # stdin redirection
        if isinstance(self.stdin, (str, Path)):
            redirects.append(f"< {self.stdin}")

        # stdout redirection
        if isinstance(self.stdout, (str, Path)):
            redirects.append(f"> {self.stdout}")
        elif self.stdout is DEVNULL:
            redirects.append("> /dev/null")

        # stderr redirection
        if self.stderr is STDOUT:
            redirects.append("2>&1")
        elif isinstance(self.stderr, (str, Path)):
            redirects.append(f"2> {self.stderr}")
        elif self.stderr is DEVNULL:
            redirects.append("2> /dev/null")

        # Combine command with redirections
        if redirects:
            cmd_str += " " + " ".join(redirects)

        # Add timeout information
        if self.timeout is not None:
            cmd_str += f" [timeout: {self.timeout}s]"

        return cmd_str

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"Process({self.program!r}, {', '.join(repr(arg) for arg in self.args)})"

    def _get_stdin_handle(self) -> int | IO | None:
        """Get stdin handle for subprocess."""
        if self.stdin in (None, subprocess.PIPE):
            return subprocess.PIPE
        if isinstance(self.stdin, int):
            check_fd(self.stdin, "r")
            return self.stdin
        elif isinstance(self.stdin, (str, bytes)):
            return subprocess.PIPE
        elif isinstance(self.stdin, BufferedIOBase):
            return cast(BinaryIO, self.stdin)
        elif isinstance(self.stdin, TextIOBase):
            return cast(TextIO, self.stdin)
        elif isinstance(self.stdin, Path):
            handle = open(self.stdin, "rb")
            self._opened_handles.append(handle)
            return handle

        raise InvalidArgument(f"Invalid stdin value: {self.stdin!r}")

    def _get_stdout_handle(self) -> int | IO | None:
        """Get stdout handle for subprocess."""
        if self.stdout in (None, subprocess.PIPE):
            return subprocess.PIPE
        elif self.stdout is DEVNULL:
            return subprocess.DEVNULL
        elif isinstance(self.stdout, int):
            check_fd(self.stdout, "w")
            return self.stdout
        elif isinstance(self.stdout, Path):
            handle = open(self.stdout, "wb")
            self._opened_handles.append(handle)
            return handle

        raise InvalidArgument(f"Invalid stdout value: {self.stdout!r}")

    def _get_stderr_handle(self) -> int | IO | None:
        """Get stderr handle for subprocess."""
        if self.stderr in (None, subprocess.PIPE):
            return subprocess.PIPE
        elif self.stderr is subprocess.STDOUT:
            return subprocess.STDOUT
        elif self.stderr is subprocess.DEVNULL:
            return subprocess.DEVNULL
        elif isinstance(self.stderr, int):
            check_fd(self.stderr, "w")
            return self.stderr
        elif isinstance(self.stderr, Path):
            handle = open(self.stderr, "wb")
            self._opened_handles.append(handle)
            return handle

        raise InvalidArgument(f"Invalid stderr value: {self.stderr!r}")

    def _prepare_stdin_input(self) -> str | None:
        """Prepare input for stdin."""
        if isinstance(self.stdin, str):
            return self.stdin
        elif isinstance(self.stdin, bytes):
            return self.stdin.decode() if self.text else None
        return None
