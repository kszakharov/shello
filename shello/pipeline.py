from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING, Self

from shello.exceptions import InvalidOperation, ProcessError, TimeoutError

if TYPE_CHECKING:
    from shello.process import Process


logger = logging.getLogger(__name__)


class Pipeline:
    """Class representing a pipeline of processes."""

    def __init__(self, *processes: Process, wait: bool = True) -> None:
        """Initialize Pipeline with a sequence of Process objects.

        Args:
            *processes: Process instances to form the pipeline
            wait: Whether to wait for all processes to complete (default: True)
        """
        if len(processes) < 2:
            raise ValueError("Pipeline requires at least two processes")

        self.validate(processes[0], first=True)
        for proc in processes[1:]:
            self.validate(proc, first=False)

        self.processes = list(processes)
        self._wait = wait

    def __or__(self, other) -> Self:
        """Support shell-style pipeline operator: Pipeline(...) | Process(...).

        Enables chaining processes onto existing pipelines using the | operator.
        Validates that the other operand is a Process instance.

        Args:
            other: Process instance to append to the pipeline.

        Returns:
            The pipeline instance with the new process added.

        Raises:
            TypeError: If other is not a Process instance.
        """
        from shello.process import Process

        if not isinstance(other, Process):
            return NotImplemented

        self.add(other)
        return self

    def __str__(self) -> str:
        """String representation of the pipeline.

        Returns:
            Shell-style pipeline string with processes joined by |.
        """
        return " | ".join(str(proc) for proc in self.processes)

    def __repr__(self) -> str:
        """Detailed representation of the pipeline.

        Returns:
            Python representation showing Pipeline constructor call.
        """
        return f"Pipeline({', '.join(repr(proc) for proc in self.processes)})"

    def add(self, process: Process) -> None:
        """Add a Process to the pipeline.

        Validates the process can be added (not already executed, proper I/O configuration)
        and appends it to the pipeline's process list.

        Args:
            process: Process instance to add.

        Raises:
            InvalidOperation: If process is already executed or has invalid I/O configuration.
        """
        self.validate(process, first=False)
        self.processes.append(process)

    @staticmethod
    def validate(process: Process, first: bool) -> None:
        """Validate that the process can be added to the pipeline.

        Ensures the process hasn't been executed and has proper I/O configuration
        for pipeline chaining. Non-first processes can't have stdin configured,
        and no process can have stdout configured (will be set to PIPE).

        Args:
            process: Process instance to validate.
            first: Whether this is the first process in the pipeline.

        Raises:
            InvalidOperation: If process has invalid configuration for pipeline.
        """
        if not first:
            if process.stdin not in (None, subprocess.PIPE):
                raise InvalidOperation("Process stdin already configured")

        if process.stdout not in (None, subprocess.PIPE):
            raise InvalidOperation("Process stdout already configured")

        if process.is_started:
            raise InvalidOperation("Process has already been executed")

    @property
    def stdout_data(self) -> str | bytes:
        """Get captured stdout."""
        if not self.is_done:
            raise InvalidOperation("Pipeline not fully executed")
        return self.processes[-1].stdout_data

    @property
    def stderr_data(self) -> str | bytes:
        """Get captured stderr."""
        if not self.is_done:
            raise InvalidOperation("Pipeline not fully executed")
        return self.processes[-1].stderr_data

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
        """Execute the pipeline of processes.

        Configures each process to pipe stdout to stdin of the next process,
        starts all processes, and optionally waits for completion.
        The last process captures stdout, intermediate processes don't.

        Returns:
            The pipeline instance itself for method chaining.

        Raises:
            ProcessError: If any process fails to execute.
            TimeoutError: If any process times out.
        """
        prev_stdout = None

        for process in self.processes:
            process._wait = False
            process.capture_stdout = False if process is not self.processes[-1] else process.capture_stdout
            process.stdin = prev_stdout if process is not self.processes[0] else process.stdin
            process.check = False if process is not self.processes[-1] else process.check
            process.stdout = subprocess.PIPE

            process.execute()

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
