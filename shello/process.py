"""Process execution and management."""

from __future__ import annotations

import errno
import functools
import logging
import os
import subprocess
import threading
from collections.abc import Container
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, TextIO

from .exceptions import InvalidArgument, InvalidOperation, ProcessError

logger = logging.getLogger(__name__)


def eintr_retry(func):
    """Retry system calls interrupted by EINTR."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        while True:
            try:
                return func(*args, **kwargs)
            except OSError as e:
                if e.errno != errno.EINTR:
                    raise

    return wrapper


class _DevNullType:
    """Singleton type for /dev/null redirection."""

    def __repr__(self) -> str:
        return "DEVNULL"


class _StdoutType:
    """Singleton type for stdout redirection."""

    def __repr__(self) -> str:
        return "STDOUT"


class _StderrType:
    """Singleton type for stderr redirection."""

    def __repr__(self) -> str:
        return "STDERR"


# Singleton instances
DEVNULL = _DevNullType()
STDOUT = _StdoutType()
STDERR = _StderrType()

# Acceptable exit codes - range(256) represents any valid exit code
ANY_EXITCODE = range(256)


class ProcessState(Enum):
    """Process execution states with numeric values for easy comparison."""

    PENDING = 0  # Initial state, no resources allocated
    SPAWNING = 1  # Transitional state during fork()
    RUNNING = 2  # Process executing with PID
    TERMINATED = 3  # Process finished, cleaned up


# Type aliases for better readability
InputStream = str | bytes | TextIO | BinaryIO | None
OutputStream = str | Path | TextIO | BinaryIO | None | _DevNullType | _StdoutType | _StderrType | int


class Process:
    """Represents a process that can be executed."""

    lock = threading.RLock()

    def __init__(
        self,
        program: str,
        *args: str,
        stdin: InputStream = None,  # type: ignore[arg-type]
        stdout: OutputStream = None,  # type: ignore[arg-type]
        stderr: OutputStream = None,  # type: ignore[arg-type]
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
        ok_exitcodes: Container[int] | int = 0,
        text: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Initialize a Process.

        Args:
            program: The program to execute
            *args: Command line arguments for program
            stdin: Input source (DEVNULL, string, file-like object)
            stdout: Output destination (None, file, path, STDOUT, STDERR)
            stderr: Error output destination (None, file, path, STDOUT, STDERR)
            cwd: Working directory
            env: Environment variables
            check: Whether to raise exception on non-zero exit
            ok_exitcodes: Acceptable exit codes (default: 0, use ANY_EXITCODE for any) - can be int or container
            text: Whether to treat I/O as text
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
        self.kwargs = kwargs

        # pipeline support
        self.previous_process: Process | None = None
        self.next_process: Process | None = None

        # Runtime state
        self._process: subprocess.Popen[str] | None = None
        self._stdout_data: str | None = None
        self._stderr_data: str | None = None
        self._state: ProcessState = ProcessState.PENDING

        # Resource management
        self._opened_handles: list[TextIO] = []

    def __or__(self, other: Process) -> Process:
        """Support shell-style pipeline operator: cmd1 | cmd2."""
        if not isinstance(other, Process):
            return NotImplemented

        # Configure stdout of this process to be stdin of the other
        if self.stdout is not None and self.stdout is not STDOUT:
            raise InvalidOperation("Process stdout already configured")

        if other.stdin is not None and other.stdin is not DEVNULL:
            raise InvalidOperation("Other process stdin already configured")

        # Create a pipeline
        self.stdout = subprocess.PIPE
        other.stdin = subprocess.PIPE

        # Store reference to pipeline source for execution
        other.previous_process = self
        self.next_process = other

        return other

    def execute(self) -> Process:
        """Execute process and wait for completion."""

        logger.debug(f"Executing {self}")
        with self.lock:
            if self.state is not ProcessState.PENDING:
                raise InvalidOperation("Process already executed")
            self.state = ProcessState.SPAWNING

            # Validate stdin early while holding lock
            self._validate_stdin()

            # Execute pipeline source first if this is part of a pipeline
            if self.previous_process:
                self.previous_process.execute()

        try:
            stdin = self.previous_process._process.stdout if self.previous_process else self._get_stdin_handle()
            self._process = subprocess.Popen(
                [self.program] + self.args,
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=self._get_stderr_handle(),
                cwd=self.cwd,
                env=self.env,
                text=self.text,
                **self.kwargs,
            )
            self.state = ProcessState.RUNNING
            logger.debug(f"Process started. PID: {self.pid}")

            if self.previous_process:
                self.previous_process._process.stdout.close()

            if not self.next_process:
                self._stdout_data, self._stderr_data = self._process.communicate()
                logger.debug(f"Process communicate done: {self}")
                self.state = ProcessState.TERMINATED
                logger.debug(f"Process terminated: {self}")

            if not self.next_process:
                if self.check and self.returncode not in self.ok_exitcodes:
                    logger.debug(f"Process exit code is not allowed: {self.returncode}")
                    raise ProcessError(
                        command=[self.program] + self.args,
                        exit_code=self.returncode,
                        stdout=self._stdout_data,
                        stderr=self._stderr_data,
                    )

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
            if self.state != ProcessState.TERMINATED:
                self.state = ProcessState.TERMINATED
                logger.debug(f"Process terminated: {self}")
            self._cleanup_resources()

        return self

    @property
    def state(self) -> ProcessState:
        """Get current process state."""

        return self._state

    @state.setter
    def state(self, new_state: ProcessState) -> None:
        """Thread-safe state transition."""

        logger.debug(f"Process state change: {self.state} -> {new_state}")
        with self.lock:
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

    def wait(self) -> Process:
        """Wait for process completion and return exit code."""
        if self._process is None:
            raise InvalidOperation("Process not started")
        if self.state is not ProcessState.TERMINATED:
            return self.execute()
        return self

    def kill(self, signal: int = 15) -> None:
        """Send signal to the process."""
        with self.lock:
            if self.state not in {ProcessState.RUNNING, ProcessState.SPAWNING}:
                raise InvalidOperation("Process not executed")

            if self._process is None or self._process.pid is None:
                raise InvalidOperation("Process not available for killing")

            self._process.send_signal(signal)
            self.state = ProcessState.TERMINATED

    @property
    def pid(self) -> int | None:
        """Get process ID."""
        return self._process.pid if self._process else None

    @property
    def stdout_data(self) -> str:
        """Get captured stdout."""
        if self.state is not ProcessState.TERMINATED:
            raise InvalidOperation("Process not executed")
        return self._stdout_data or ""

    @property
    def stderr_data(self) -> str:
        """Get captured stderr."""
        if self.state is not ProcessState.TERMINATED:
            raise InvalidOperation("Process not executed")

        # TODO: capture stderr from pipeline source if needed
        # Combine current stderr with source stderr for pipelines
        stderr_parts = []
        if hasattr(self, "_source_stderr") and self._source_stderr:
            stderr_parts.append(self._source_stderr)
        if self._stderr_data:
            stderr_parts.append(self._stderr_data)

        return "".join(stderr_parts)

    @property
    def returncode(self) -> int:
        """Get process return code."""
        if self.state is not ProcessState.TERMINATED:
            raise InvalidOperation("Process not executed")
        return self._process.returncode if self._process else -1

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
        elif self.stdout is STDERR:
            redirects.append(">&2")

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

        # Add pipeline if this is the end of a pipeline
        if self.previous_process:
            cmd_str = f"{self.previous_process} | {cmd_str}"

        return cmd_str

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"Process({self.program!r}, {self.args!r})"

    def _get_stdin_handle(self) -> int | None:
        """Get stdin handle for subprocess."""
        if self.stdin is DEVNULL:
            return subprocess.DEVNULL
        elif isinstance(self.stdin, (str, bytes)):
            # Create a pipe
            r_fd, w_fd = os.pipe()

            # Write data to the write end
            if isinstance(self.stdin, str):
                os.write(w_fd, self.stdin.encode())
            else:
                os.write(w_fd, self.stdin)
            os.close(w_fd)
            return r_fd

        elif hasattr(self.stdin, "read"):
            return self.stdin
        elif self.stdin is None:
            return None
        else:
            return subprocess.PIPE

    def _get_stdout_handle(self) -> int | TextIO | None:
        """Get stdout handle for subprocess."""
        if self.stdout is DEVNULL:
            return subprocess.DEVNULL
        elif isinstance(self.stdout, (str, Path)):
            handle = open(self.stdout, "w")
            self._opened_handles.append(handle)
            return handle
        elif hasattr(self.stdout, "write"):
            return self.stdout
        elif self.stdout is subprocess.PIPE or self.stdout is None:
            return subprocess.PIPE
        else:
            return subprocess.PIPE

    def _get_stderr_handle(self) -> int | TextIO | None:
        """Get stderr handle for subprocess."""
        if self.stderr is DEVNULL:
            return subprocess.DEVNULL
        elif self.stderr is STDOUT:
            return subprocess.STDOUT
        elif isinstance(self.stderr, (str, Path)):
            handle = open(self.stderr, "w")
            self._opened_handles.append(handle)
            return handle
        elif hasattr(self.stderr, "write"):
            return self.stderr
        elif self.stderr is subprocess.PIPE or self.stderr is None:
            return subprocess.PIPE
        else:
            return subprocess.PIPE

    def _validate_stdin(self) -> None:
        """Validate stdin input type."""
        # Only allow specific int constants like subprocess.PIPE, not arbitrary ints
        is_valid_int = isinstance(self.stdin, int) and self.stdin == subprocess.PIPE

        valid_types = (
            str,
            bytes,
            type(None),
            _DevNullType,
        )

        if not (isinstance(self.stdin, valid_types) or is_valid_int or hasattr(self.stdin, "read")):
            raise InvalidArgument(f"Invalid stdin type: {type(self.stdin)}")

    def _prepare_stdin_input(self) -> str | None:
        """Prepare input for stdin."""
        if isinstance(self.stdin, str):
            return self.stdin
        elif isinstance(self.stdin, bytes):
            return self.stdin.decode() if self.text else None
        return None
