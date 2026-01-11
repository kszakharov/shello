"""Test Shell factory class."""


from shello import Process, Shell


class TestShell:
    """Test cases for Shell class."""

    def test_shell_call_method(self):
        """Test Shell __call__ method."""
        shell = Shell()
        process = shell("echo", "hello")

        assert isinstance(process, Process)
        assert process.program == "echo"
        assert process.args == ["hello"]
        assert process.stdin is not None  # Should be DEVNULL

    def test_shell_getattr_method(self):
        """Test Shell __getattr__ method."""
        shell = Shell()
        process = shell.echo("hello")

        assert isinstance(process, Process)
        assert process.program == "echo"  # underscores converted to hyphens
        assert process.args == ["hello"]

    def test_shell_getattr_with_underscores(self):
        """Test that underscores in program names are converted to hyphens."""
        shell = Shell()
        process = shell.complex_command_name("arg")

        assert isinstance(process, Process)
        assert process.program == "complex-command-name"
        assert process.args == ["arg"]

    def test_shell_with_default_options(self):
        """Test Shell with default options."""
        shell = Shell(check=False)
        process = shell.echo("hello")

        assert isinstance(process, Process)
        assert process.check is False

    def test_shell_options_override(self):
        """Test that options passed to call override defaults."""
        shell = Shell(check=False)
        process = shell.echo("hello", check=True)

        assert isinstance(process, Process)
        assert process.check is True  # Should override default

    def test_shell_kwargs_options(self):
        """Test passing options as keyword arguments."""
        shell = Shell()
        process = shell.echo("hello", cwd="/tmp")

        assert isinstance(process, Process)
        assert process.cwd == "/tmp"

    def test_shell_with_all_options(self):
        """Test Shell with various options."""
        shell = Shell(text=False, check=False)
        process = shell("echo", "hello", check=True, env={"TEST": "value"})

        assert isinstance(process, Process)
        assert process.text is False  # from default
        assert process.check is True  # overridden in call
        assert process.env == {"TEST": "value"}  # from call

    def test_shell_empty_call(self):
        """Test Shell call with no arguments."""
        shell = Shell()
        process = shell("echo")

        assert isinstance(process, Process)
        assert process.program == "echo"
        assert process.args == []

    def test_shell_getattr_empty_call(self):
        """Test Shell getattr with no arguments."""
        shell = Shell()
        process = shell.echo()

        assert isinstance(process, Process)
        assert process.program == "echo"
        assert process.args == []
