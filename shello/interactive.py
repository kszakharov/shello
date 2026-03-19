"""Interactive process execution via PTY."""

from __future__ import annotations

import logging
import os
import select
import sys
import termios
import threading
import time
import tty
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Self

from .decorators import with_callback
from .exceptions import InvalidOperation, ProcessError
from .process import Process, ProcessState

logger = logging.getLogger(__name__)


class InteractiveProcess(Process):
    """A Process subclass that uses pty.fork() for true terminal emulation.

    Unlike Process with interactive=True (which inherits the parent's file
    descriptors), InteractiveProcess forks with a pseudo-terminal, enabling
    programs like SSH that require a real PTY to work correctly.
    """

    def __init__(self, program: str, *args: str, **kwargs) -> None:  # type: ignore[override]
        super().__init__(program, *args, **kwargs)
        self._pty_pid: int | None = None
        self._pty_returncode: int | None = None

    def execute(self) -> Self:
        """Execute the process using pty.fork() for PTY support."""
        import pty

        if self.state is not ProcessState.PENDING:
            logger.error("%s: execute() called in invalid state (%s)", self.program, self.state)
            raise InvalidOperation("Process already executed")

        with self._lock:
            self.state = ProcessState.SPAWNING

        try:
            pid, master_fd = pty.fork()
        except OSError as e:
            with self._lock:
                self._state = ProcessState.PENDING
            raise ProcessError(
                command=[self.program] + self.args,
                exit_code=-1,
                message=f"Failed to fork PTY: {e}",
            ) from e

        if pid == 0:
            # Child process: exec the command
            try:
                if self.cwd is not None:
                    os.chdir(str(self.cwd))
                cmd = [self.program] + self.args
                env = self.env if self.env is not None else os.environ
                os.execvpe(self.program, cmd, env)
            except Exception as e:
                import sys as _sys
                _sys.stderr.write(f"InteractiveProcess child error: {e}\n")
                _sys.stderr.flush()
            os._exit(127)

        # Parent process
        self._pty_pid = pid
        self.start_time = time.time()
        self.state = ProcessState.RUNNING

        t = threading.Thread(
            target=self._background_monitor_pty,
            args=(master_fd,),
            name=f"[{self.program} pty]",
        )
        self._threads.append(t)
        t.start()

        if self._wait:
            self.wait()

        return self

    @with_callback(on_done=lambda self: cast("InteractiveProcess", self)._task_done())
    def _background_monitor_pty(self, master_fd: int) -> None:
        """PTY proxy: relay I/O between the terminal and the child process."""
        import io

        old_settings = None

        # Determine whether stdin has a real file descriptor (not available in pytest etc.)
        stdin_fd: int | None = None
        try:
            stdin_fd = sys.stdin.fileno()
        except (io.UnsupportedOperation, AttributeError):
            stdin_fd = None

        try:
            if stdin_fd is not None:
                try:
                    old_settings = termios.tcgetattr(stdin_fd)
                    tty.setraw(stdin_fd)
                except termios.error:
                    old_settings = None

            select_reads: list[int] = [master_fd]
            if stdin_fd is not None:
                select_reads.append(stdin_fd)

            while True:
                try:
                    r, _, _ = select.select(select_reads, [], [])
                except (ValueError, OSError):
                    break

                if master_fd in r:
                    try:
                        data = os.read(master_fd, 1024)
                    except OSError:
                        break
                    if not data:
                        break
                    try:
                        os.write(sys.stdout.fileno(), data)
                    except (OSError, Exception):
                        pass

                if stdin_fd is not None and stdin_fd in r:
                    try:
                        data = os.read(stdin_fd, 1024)
                    except OSError:
                        break
                    if not data:
                        break
                    try:
                        os.write(master_fd, data)
                    except OSError:
                        break

        finally:
            if old_settings is not None and stdin_fd is not None:
                try:
                    termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
                except Exception:
                    pass
            try:
                os.close(master_fd)
            except OSError:
                pass
            while True:
                try:
                    _, status = os.waitpid(self._pty_pid, 0)  # type: ignore[arg-type]
                    self._pty_returncode = os.waitstatus_to_exitcode(status)
                    break
                except InterruptedError:
                    continue
                except ChildProcessError:
                    self._pty_returncode = -1
                    break
                except OSError:
                    self._pty_returncode = -1
                    break
            self.end_time = time.time()

    @property
    def stdout(self) -> str | bytes:
        """Not available for interactive PTY processes."""
        raise InvalidOperation("stdout is not captured in interactive PTY mode")

    @property
    def stderr(self) -> str | bytes:
        """Not available for interactive PTY processes."""
        raise InvalidOperation("stderr is not captured in interactive PTY mode")

    @property
    def returncode(self) -> int:
        """Get process return code from PTY wait."""
        if self.state is not ProcessState.TERMINATED:
            raise InvalidOperation("Process not executed")
        if self._pty_returncode is None:
            raise InvalidOperation("Process return code not available")
        return self._pty_returncode

    @property
    def pid(self) -> int | None:
        """Get process ID of the forked child."""
        return self._pty_pid

    def kill(self, signal: int = 15) -> None:
        """Send signal to the PTY child process."""
        with self._lock:
            if self.state not in {ProcessState.RUNNING, ProcessState.SPAWNING}:
                raise InvalidOperation("Process not executed")
            if self._pty_pid is None:
                raise InvalidOperation("Process not available for killing")
            try:
                os.kill(self._pty_pid, signal)
            except OSError:
                pass

    def wait(self) -> Self:
        """Wait for PTY process completion."""
        if self._pty_pid is None:
            raise InvalidOperation("Process not started")

        if not self._threads_done_event.is_set():
            self._threads_done_event.wait()

        self._check_exception()
        if self.check:
            self.check_returncode()
        return self
