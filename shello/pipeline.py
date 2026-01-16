from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING, Self

from shello.exceptions import InvalidOperation, ProcessError

if TYPE_CHECKING:
    from shello.process import Process


logger = logging.getLogger(__name__)


class Pipeline:
    """Class representing a pipeline of processes."""

    def __init__(self, *processes: Process, wait: bool = True) -> None:
        """
        Initialize Pipeline with a sequence of Process objects.

        Args:
            *processes: Process instances to form the pipeline
        """
        if len(processes) < 2:
            raise ValueError("Pipeline requires at least two processes")

        self.validate(processes[0], first=True)
        for proc in processes[1:]:
            self.validate(proc, first=False)

        self.processes = list(processes)
        self._wait = wait

    def __or__(self, other) -> Self:
        """Support shell-style pipeline operator: Pipeline(...) | Process(...)."""
        from shello.process import Process

        if not isinstance(other, Process):
            return NotImplemented

        self.add(other)
        return self

    def __str__(self) -> str:
        """String representation of the pipeline."""
        return " | ".join(str(proc) for proc in self.processes)

    def __repr__(self) -> str:
        """Detailed representation of the pipeline."""
        return f"Pipeline({', '.join(repr(proc) for proc in self.processes)})"

    def add(self, process: Process) -> None:
        """
        Add a Process to the pipeline.

        Args:
            process: Process instance to add
        """
        self.validate(process, first=False)
        self.processes.append(process)

    @staticmethod
    def validate(process: Process, first: bool) -> None:
        """
        Validate that the process can be added to the pipeline.

        Args:
            process: Process instance to validate
            first: Whether this is the first process in the pipeline
        """
        if not first:
            if process.stdin not in (None, subprocess.PIPE):
                raise InvalidOperation("Process stdin already configured")

        if process.stdout not in (None, subprocess.PIPE):
            raise InvalidOperation("Process stdout already configured")

        if process.is_started:
            raise InvalidOperation("Process has already been executed")

    @property
    def stdout_data(self) -> str:
        """Get captured stdout."""
        if not self.is_done:
            raise InvalidOperation("Pipeline not fully executed")
        return "".join(proc.stdout_data for proc in self.processes)

    @property
    def stderr_data(self) -> str:
        """Get captured stderr."""
        if not self.is_done:
            raise InvalidOperation("Pipeline not fully executed")
        return "".join(proc.stderr_data for proc in self.processes)

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
        """
        Execute the pipeline of processes.

        Returns:
            The pipeline instance itself
        """
        prev_stdout = None

        for process in self.processes:
            process._wait = False
            process.stdin = prev_stdout or process.stdin
            process.stdout = subprocess.PIPE

            process.execute()

            if prev_stdout is not None:
                prev_stdout.close()

            prev_stdout = process._process.stdout

        if self._wait:
            self.wait()

        return self

    def wait(self) -> Self:
        """
        Wait for all processes in the pipeline to complete.

        Returns:
            The pipeline instance itself
        """
        for process in self.processes:
            try:
                process.wait()
            except ProcessError as e:
                logger.debug(f"Error waiting for process: {e}")
        return self
