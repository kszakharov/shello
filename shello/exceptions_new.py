"""Exception classes for the shello library."""

from __future__ import annotations

from typing import Any


class ShellError(Exception):
    """Base exception for all shell library errors."""

    def __init__(self, message: str, *args: object) -> None:
        """Initialize ShellError with optional format arguments.

        Args:
            message: Error message format string (can contain {} placeholders).
            *args: Arguments to format into the message string.
        """
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
        """Initialize ProcessError with execution details.

        Args:
            command: List of command and arguments that failed..
            exit_code: Process exit code..
            stdout: Captured stdout output (optional)..
            stderr: Captured stderr output (optional)..
            message: Custom error message (auto-generated if None)..
        """
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

    def __init__(self, message: str, *args: object) -> None:
        """Initialize InvalidArgument with error message.

        Args:
            message: Error message format string.
            *args: Arguments to format into the message string.
        """
        super().__init__(message, *args)


class InvalidOperation(ShellError):
    """Raised when an invalid operation is attempted."""

    def __init__(self, message: str, *args: object) -> None:
        """Initialize InvalidOperation with error message.

        Args:
            message: Error message format string.
            *args: Arguments to format into the message string.
        """
        super().__init__(message, *args)


class TimeoutError(ShellError):
    """Raised when a process times out."""

    def __init__(self, message: str, *args: object) -> None:
        """Initialize TimeoutError with error message.

        Args:
            message: Error message format string.
            *args: Arguments to format into the message string.
        """
        super().__init__(message, *args)


class UnexpectedExitCodeError(ShellError):
    """Raised when a process exits with an unexpected return code."""

    def __init__(self, exit_code: int, expected_codes: Any, message: str | None = None) -> None:
        """Initialize UnexpectedExitCodeError with exit code details.

        Args:
            exit_code: The actual exit code returned by the process.
            expected_codes: Container of acceptable exit codes.
            message: Custom error message (auto-generated if None).
        """
        if message is None:
            try:
                # Try to iterate over expected_codes for display
                codes_list = list(expected_codes)
                expected_str = ", ".join(str(code) for code in sorted(codes_list))
            except (TypeError, AttributeError):
                # Fallback for non-iterable cases
                expected_str = str(expected_codes)
            message = f"Process exited with code {exit_code}, expected one of: {expected_str}"

        super().__init__(message)
        self.exit_code = exit_code
        self.expected_codes = expected_codes


class AlreadyRunError(Exception):
    """Raised when a run-once method is called more than once."""

    def __init__(self, message: str) -> None:
        """Initialize AlreadyRunError with error message.

        Args:
            message: Error message describing the repeated method call.
        """
        super().__init__(message)
