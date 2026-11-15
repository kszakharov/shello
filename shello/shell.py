"""Shell factory class for creating Command objects."""

from __future__ import annotations

from typing import Any

from .command import Command


class Shell:
    """Factory class for creating Command objects with shell-like syntax."""

    def __init__(self, **default_options: Any) -> None:
        """Initialize Shell with default options.

        Args:
            **default_options: Default options for all created commands
        """
        self.default_options = default_options

    def __call__(self, program: str, *args: str, **kwargs: Any) -> Command:
        """Create a Command with the given program and arguments.

        Args:
            program: The program to execute
            *args: Command line arguments
            **kwargs: Command configuration options

        Returns:
            Command instance
        """
        # Merge default options with provided options
        options = self.default_options.copy()
        options.update(kwargs)

        return Command(program, *args, **options)

    def __getattr__(self, program: str):
        """Create a callable that returns a Command using attribute access.

        Enables shell-like syntax: sh.echo("hello") or sh.git("status").
        Converts underscores to hyphens for command names.

        Args:
            program: The program name (underscores converted to hyphens).

        Returns:
            Callable that creates Command instances with the program name.
        """
        # Convert underscores to hyphens for command names
        program_name = program.replace("_", "-")

        def create_command(*args: str, **kwargs: Any) -> Command:
            """Create a Command with the program name.

            Args:
                *args: Command line arguments for the program
                **kwargs: Command configuration options (merged with shell defaults)

            Returns:
                Command instance with configured program name and arguments
            """

            options = self.default_options.copy()
            options.update(kwargs)
            return Command(program_name, *args, **options)

        return create_command


binary_shell = Shell()
shell = Shell(text=True)
