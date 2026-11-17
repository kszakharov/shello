"""Test Shell factory class."""

from shello import Command, Shell


class TestShell:
    """Test cases for Shell class."""

    def test_shell_call_method(self):
        """Test Shell __call__ method."""
        shell = Shell()
        command = shell("echo", "hello")

        assert isinstance(command, Command)
        assert command.program == "echo"
        assert command.args == ("hello",)

    def test_shell_getattr_method(self):
        """Test Shell __getattr__ method."""
        shell = Shell()
        command = shell.echo("hello")

        assert isinstance(command, Command)
        assert command.program == "echo"  # underscores converted to hyphens
        assert command.args == ("hello",)

    def test_shell_getattr_with_underscores(self):
        """Test that underscores in program names are converted to hyphens."""
        shell = Shell()
        command = shell.complex_command_name("arg")

        assert isinstance(command, Command)
        assert command.program == "complex-command-name"
        assert command.args == ("arg",)

    def test_shell_with_default_options(self):
        """Test Shell with default options."""
        shell = Shell(check=False)
        command = shell.echo("hello")

        assert isinstance(command, Command)
        assert command.check is False

    def test_shell_options_override(self):
        """Test that options passed to call override defaults."""
        shell = Shell(check=False)
        command = shell.echo("hello", check=True)

        assert isinstance(command, Command)
        assert command.check is True  # Should override default

    def test_shell_kwargs_options(self):
        """Test passing options as keyword arguments."""
        shell = Shell()
        command = shell.echo("hello", cwd="/tmp")

        assert isinstance(command, Command)
        assert command.cwd == "/tmp"

    def test_shell_with_all_options(self):
        """Test Shell with various options."""
        shell = Shell(text=False, check=False)
        command = shell("echo", "hello", check=True, env={"TEST": "value"})

        assert isinstance(command, Command)
        assert command.text is False  # from default
        assert command.check is True  # overridden in call
        assert command.env == {"TEST": "value"}  # from call

    def test_shell_empty_call(self):
        """Test Shell call with no arguments."""
        shell = Shell()
        command = shell("echo")

        assert isinstance(command, Command)
        assert command.program == "echo"
        assert command.args == ()

    def test_shell_getattr_empty_call(self):
        """Test Shell getattr with no arguments."""
        shell = Shell()
        command = shell.echo()

        assert isinstance(command, Command)
        assert command.program == "echo"
        assert command.args == ()
