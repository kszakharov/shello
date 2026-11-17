"""Configure and execute commands."""

from __future__ import annotations

from collections.abc import Container
from pathlib import Path
from typing import Any, AnyStr

from .pipeline import Pipeline
from .process import DEVNULL, STDOUT, Process
from .types import FileDescriptorLike


class Command:
    """Represents a command that can be executed."""

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
        """Initialize a Command.

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
        self.args = args
        self._stdin_source = stdin
        self._stdout_destination = stdout
        self._stderr_destination = stderr
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
        self.wait = wait
        self.kwargs = kwargs

    def __or__(self, other: Command) -> Pipeline:
        """Support shell-style pipeline operator: cmd1 | cmd2.

        Args:
            other: Command to pipe stdout into

        Returns:
            Pipeline connecting this command to the other

        Notes:
            If `other` is not a Command instance, returns NotImplemented
            to allow Python to handle the operation with the reflected method.
        """

        if not isinstance(other, Command):
            return NotImplemented

        return Pipeline(self, other)

    def execute(self) -> Process:
        """Execute the command.

        Starts the Process.
        If wait=True, blocks until completion.

        Returns:
            An instance of Process
        """

        process = Process(command=self)
        if self.wait:
            process.wait()
        return process

    def __str__(self) -> str:
        """String representation of the command."""
        # Build base command
        cmd_parts = (self.program, *self.args)
        cmd_str = " ".join(cmd_parts)

        # Add I/O redirections
        redirects = []

        # stdin redirection
        if isinstance(self._stdin_source, (str, Path)):
            redirects.append(f"< {self._stdin_source}")

        # stdout redirection
        if isinstance(self._stdout_destination, (str, Path)):
            redirects.append(f"> {self._stdout_destination}")
        elif self._stdout_destination is DEVNULL:
            redirects.append("> /dev/null")

        # stderr redirection
        if self._stderr_destination is STDOUT:
            redirects.append("2>&1")
        elif isinstance(self._stderr_destination, (str, Path)):
            redirects.append(f"2> {self._stderr_destination}")
        elif self._stderr_destination is DEVNULL:
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
        return f"Command({self.program!r}, {', '.join(repr(arg) for arg in self.args)})"
