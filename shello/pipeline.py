from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self

from shello.exceptions import InvalidOperation, ProcessError, TimeoutError

if TYPE_CHECKING:
    from shello.command import Command
    from shello.process import Process


logger = logging.getLogger(__name__)


class Pipeline:
    """Class representing a pipeline of commands."""

    def __init__(self, *commands: Command, wait: bool = True) -> None:
        """Initialize Pipeline with a sequence of Command objects.

        Args:
            *commands: Command instances to form the pipeline
            wait: Whether to wait for all processes to complete (default: True)
        """

        if len(commands) < 2:
            raise ValueError("Pipeline requires at least two commands")

        self.validate(commands[0], first=True)
        for command in commands[1:]:
            self.validate(command, first=False)

        self.commands: list[Command] = list(commands)
        self._wait: bool = wait

        self.processes: list[Process] = list()

    def __or__(self, other) -> Self:
        """Support shell-style pipeline operator: Pipeline(...) | Command(...).

        Enables chaining command onto existing pipelines using the | operator.
        Validates that the other operand is a Command instance.

        Args:
            other: Command instance to append to the pipeline.

        Returns:
            The pipeline instance with the new command added.

        Raises:
            TypeError: If other is not a Command instance.
        """

        from shello.command import Command

        if not isinstance(other, Command):
            return NotImplemented

        self.add(other)
        return self

    def __str__(self) -> str:
        """String representation of the pipeline.

        Returns:
            Shell-style pipeline string with commands joined by |.
        """
        return " | ".join(str(command) for command in self.commands)

    def __repr__(self) -> str:
        """Detailed representation of the pipeline.

        Returns:
            Python representation showing Pipeline constructor call.
        """
        return f"Pipeline({', '.join(repr(command) for command in self.commands)})"

    def add(self, command: Command) -> None:
        """Add a Command to the pipeline.

        Validates the command can be added (proper I/O configuration)
        and appends it to the pipeline's command list.

        Args:
            command: Command instance to add.

        Raises:
            InvalidOperation: If command has invalid I/O configuration.
        """

        self.validate(command, first=False)
        self.commands.append(command)

    @staticmethod
    def validate(command: Command, first: bool) -> None:
        """Validate that the command can be added to the pipeline.

        Ensures the command has proper I/O configuration for pipeline chaining.
        Non-first command can't have stdin configured,
        and no command can have stdout configured (will be set to PIPE).

        Args:
            command: Command instance to validate.
            first: Whether this is the first command in the pipeline.

        Raises:
            InvalidOperation: If command has invalid configuration for pipeline.
        """

        if not first:
            if command._stdin_source not in (None, subprocess.PIPE):
                raise InvalidOperation("Command stdin already configured")

        if command._stdout_destination not in (None, subprocess.PIPE):
            raise InvalidOperation("Command stdout already configured")

    @property
    def stdout(self) -> str | bytes:
        """Get captured stdout."""
        if not self.is_done:
            raise InvalidOperation("Pipeline not fully executed")
        return self.processes[-1].stdout

    @property
    def stderr(self) -> str | bytes:
        """Get captured stderr."""
        if not self.is_done:
            raise InvalidOperation("Pipeline not fully executed")
        return self.processes[-1].stderr

    @property
    def returncode(self) -> int:
        """Get return code of the last process in the pipeline."""
        if not self.is_done:
            raise InvalidOperation("Pipeline not fully executed")
        return self.processes[-1].returncode

    @property
    def is_done(self) -> bool:
        """Check if all processes in the pipeline have terminated."""
        return all(proc.is_done for proc in self.processes)

    @property
    def is_successful(self) -> bool:
        """Check if all processes in the pipeline executed successfully."""
        if not self.is_done:
            raise InvalidOperation("Pipeline not fully executed")
        return all(proc.returncode == 0 for proc in self.processes)

    @property
    def is_failed(self) -> bool:
        """Check if any process in the pipeline failed."""
        return not self.is_successful

    def execute(self) -> Self:
        """Execute the pipeline of commands.

        Configures each command to pipe stdout to stdin of the next command,
        starts all commands, and optionally waits for completion.
        The last process captures stdout, intermediate processes don't.

        Returns:
            The pipeline instance itself for method chaining.

        Raises:
            ProcessError: If any process fails to execute.
            TimeoutError: If any process times out.
        """

        prev_stdout = None

        for command in self.commands:
            command.wait = False
            command.capture_stdout = False if command is not self.commands[-1] else command.capture_stdout
            command._stdin_source = prev_stdout if command is not self.commands[0] else command._stdin_source
            command.check = False if command is not self.commands[-1] else command.check
            command._stdout_destination = subprocess.PIPE

            process = command.execute()
            self.processes.append(process)

            if prev_stdout is not None:
                prev_stdout.close()

            prev_stdout = process._process.stdout

        if self._wait:
            self.wait()

        return self

    def wait(self) -> Self:
        """Wait for all processes in the pipeline to complete.

        Iterates through all processes and waits for each to finish.
        Logs completion and propagates any errors that occur.

        Returns:
            The pipeline instance itself for method chaining.

        Raises:
            TimeoutError: If any process times out while waiting.
            ProcessError: If any process fails during execution.
        """
        for process in self.processes:
            logger.debug("%s: waiting for process (state=%s)", process, process.state)
            try:
                process.wait()
                logger.info("%s: process completed (exit_code=%s, state=%s)", process, process.returncode, process.state)
            except TimeoutError:
                logger.debug("%s: process timed out (state=%s)", process, process.state)
                raise
            except ProcessError as e:
                logger.error("%s: process failed (state=%s)", process, process.state)
                logger.error("%s: process error details", process, exc_info=e)
                raise
        logger.info("All processes have completed")
        return self
