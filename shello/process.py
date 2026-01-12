"""Process execution and management."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, TextIO, cast

from .exceptions import InvalidArgument, InvalidOperation, ProcessError


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

# Type aliases for better readability
InputStream = str | bytes | TextIO | None | _DevNullType | int
OutputStream = (
    str | Path | TextIO | None | _DevNullType | _StdoutType | _StderrType | int
)


class Process:
    """Represents a process that can be executed."""

    def __init__(
        self,
        program: str,
        *args: str,
        stdin: InputStream = DEVNULL,
        stdout: OutputStream = None,
        stderr: OutputStream = None,
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
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
        self.text = text
        self.kwargs = kwargs

        # Runtime state
        self._process: subprocess.Popen[str] | None = None
        self._stdout_data: str | None = None
        self._stderr_data: str | None = None
        self._executed = False
        self._pipeline_source: Process | None = None

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
        other._pipeline_source = self

        return other

    def execute(self) -> Process:
        """Execute process and wait for completion."""
        if self._executed:
            raise InvalidOperation("Process already executed")

        # Validate stdin early
        self._validate_stdin()

        # Execute pipeline source first if this is part of a pipeline
        if self._pipeline_source:
            self._pipeline_source.execute()

        try:
            self._process = subprocess.Popen(  # type: ignore[arg-type]
                [self.program] + self.args,
                stdin=cast(Any, self._get_stdin_handle()),
                stdout=cast(Any, self._get_stdout_handle()),
                stderr=cast(Any, self._get_stderr_handle()),
                cwd=self.cwd,
                env=self.env,
                text=self.text,
                **self.kwargs,
            )

            # Handle pipeline communication
            if self._pipeline_source and self._pipeline_source._process:
                # For pipeline, communicate between processes
                source_stdout, source_stderr = (
                    self._pipeline_source._process.communicate()
                )
                self._stdout_data, self._stderr_data = self._process.communicate(
                    source_stdout
                )
                # Store stderr from source process for access via stderr_data()
                self._source_stderr = source_stderr
            else:
                # Normal execution with stdin
                stdin_input = self._prepare_stdin_input()
                self._stdout_data, self._stderr_data = self._process.communicate(
                    stdin_input
                )

            self._executed = True

            # Check exit code if requested
            if self.check and self._process.returncode != 0:
                raise ProcessError(
                    command=[self.program] + self.args,
                    exit_code=self._process.returncode,
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
            raise ProcessError(
                command=[self.program] + self.args, exit_code=-1, message=str(e)
            ) from e

        return self

    def wait(self) -> int:
        """Wait for process completion and return exit code."""
        if not self._executed:
            self.execute()
        return self._process.returncode if self._process else -1

    def kill(self, signal: int = 15) -> None:
        """Send signal to the process."""
        if self._process is None:
            raise InvalidOperation("Process not executed")
        if self._process.pid is not None:
            self._process.send_signal(signal)

    @property
    def pid(self) -> int | None:
        """Get process ID."""
        return self._process.pid if self._process else None

    @property
    def stdout_data(self) -> str:
        """Get captured stdout."""
        if not self._executed:
            raise InvalidOperation("Process not executed")
        return self._stdout_data or ""

    @property
    def stderr_data(self) -> str:
        """Get captured stderr."""
        if not self._executed:
            raise InvalidOperation("Process not executed")

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
        if not self._executed:
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
        if self._pipeline_source:
            cmd_str = f"{self._pipeline_source} | {cmd_str}"

        return cmd_str

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"Process({self.program!r}, {self.args!r})"

    def _get_stdin_handle(self):
        """Get stdin handle for subprocess."""
        if self.stdin is DEVNULL:
            return subprocess.DEVNULL
        elif isinstance(self.stdin, (str, bytes)):
            return subprocess.PIPE
        elif hasattr(self.stdin, "read"):
            return self.stdin
        elif self.stdin is None:
            return None
        else:
            return subprocess.PIPE

    def _get_stdout_handle(self):
        """Get stdout handle for subprocess."""
        if self.stdout is DEVNULL:
            return subprocess.DEVNULL
        elif isinstance(self.stdout, (str, Path)):
            return open(self.stdout, "w")
        elif hasattr(self.stdout, "write"):
            return self.stdout
        elif self.stdout is subprocess.PIPE or self.stdout is None:
            return subprocess.PIPE
        else:
            return subprocess.PIPE

    def _get_stderr_handle(self):
        """Get stderr handle for subprocess."""
        if self.stderr is DEVNULL:
            return subprocess.DEVNULL
        elif self.stderr is STDOUT:
            return subprocess.STDOUT
        elif isinstance(self.stderr, (str, Path)):
            return open(self.stderr, "w")
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

        if not (
            isinstance(self.stdin, valid_types)
            or is_valid_int
            or hasattr(self.stdin, "read")
        ):
            raise InvalidArgument(f"Invalid stdin type: {type(self.stdin)}")

    def _prepare_stdin_input(self) -> str | None:
        """Prepare input for stdin."""
        if isinstance(self.stdin, str):
            return self.stdin
        elif isinstance(self.stdin, bytes):
            return self.stdin.decode() if self.text else None
        return None
