"""Exception classes for the shello library."""

from __future__ import annotations


class ShellError(Exception):
    """Base exception for all shell library errors."""

    def __init__(self, message: str, *args: object) -> None:
        super().__init__(message.format(*args) if args else message)
        self.message = message


class ProcessError(ShellError):
    """Raised when a process fails to execute or returns non-zero exit status."""

    def __init__(
        self,
        command: list[str],
        exit_code: int,
        stdout: str | None = None,
        stderr: str | None = None,
        message: str | None = None,
    ) -> None:
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

        if message is None:
            message = f"Command {' '.join(command)} failed with exit code {exit_code}"
            if stderr:
                message += f": {stderr}"

        super().__init__(message)


class InvalidArgument(ShellError, ValueError):
    """Raised when invalid arguments are provided to a process."""

    pass


class InvalidOperation(ShellError):
    """Raised when an invalid operation is attempted."""

    pass


class TimeoutError(ShellError):
    """Raised when a process times out."""

    pass
