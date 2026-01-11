"""Shell factory class for creating Process objects."""

from __future__ import annotations

from typing import Any

from .process import Process


class Shell:
    """Factory class for creating Process objects with shell-like syntax."""

    def __init__(self, **default_options: Any) -> None:
        """
        Initialize Shell with default options.

        Args:
            **default_options: Default options for all created processes
        """
        self.default_options = default_options

    def __call__(self, program: str, *args: str, **kwargs: Any) -> Process:
        """
        Create a Process with the given program and arguments.

        Args:
            program: The program to execute
            *args: Command line arguments
            **kwargs: Process configuration options

        Returns:
            Process instance
        """
        # Merge default options with provided options
        options = self.default_options.copy()
        options.update(kwargs)

        return Process(program, *args, **options)

    def __getattr__(self, program: str):
        """
        Create a callable that returns a Process using attribute access.

        Args:
            program: The program name (underscores converted to hyphens)

        Returns:
            Callable that creates Process instances
        """
        # Convert underscores to hyphens for command names
        program_name = program.replace("_", "-")

        def create_process(*args: str, **kwargs: Any) -> Process:
            """Create a Process with the program name."""
            options = self.default_options.copy()
            options.update(kwargs)
            return Process(program_name, *args, **options)

        return create_process
