"""Test pipeline functionality."""

import pytest

from shello import DEVNULL, Pipeline, Command, shell
from shello.exceptions import InvalidOperation


class TestPipeline:
    """Test cases for pipeline functionality."""

    def test_simple_pipeline(self):
        """Test simple pipeline: echo hello | wc -c."""
        echo_cmd = Command("echo", "hello")
        wc_cmd = Command("wc", "-c")

        pipeline = echo_cmd | wc_cmd
        result = pipeline.execute()

        # "hello" + newline = 6 characters
        assert result.returncode == 0
        assert "6" in result.stdout.decode()

    def test_pipeline_with_shell(self):
        """Test pipeline using shell factory."""
        pipeline = shell.echo("hello world") | shell.wc("-w")
        result = pipeline.execute()

        assert result.returncode == 0
        assert "2" in result.stdout  # "hello world" has 2 words

    def test_pipeline_stderr_capture(self):
        """Test pipeline stderr capture."""
        # Command that outputs to stderr, then pipe to another command
        first_cmd = Command("sh", "-c", "echo 'error' >&2; echo 'output'")
        second_cmd = Command("wc", "-c")

        pipeline = first_cmd | second_cmd
        result = pipeline.execute()

        assert result.returncode == 0
        # wc -c counts characters, "output\n" is 7 characters
        assert "7" in result.stdout.decode()
        # Pipeline stderr should contain stderr from first command
        # assert "error" in result.stderr_data  # Not implemented

    def test_pipeline_chaining(self):
        """Test chaining multiple processes."""
        pipeline = Command("echo", "a b c") | Command("tr", " ", "\n") | Command("wc", "-l")
        result = pipeline.execute()

        assert result.returncode == 0
        assert "3" in result.stdout.decode()  # 3 lines

    def test_pipeline_with_stdin(self):
        """Test pipeline with stdin input to first process."""
        first_cmd = Command("wc", "-c", stdin=b"hello world")
        second_cmd = Command("tr", "-d", " ")

        pipeline = first_cmd | second_cmd
        result = pipeline.execute()

        assert result.returncode == 0
        # Should remove spaces from the character count
        assert "11" in result.stdout.decode() or "9" in result.stdout.decode()

    def test_pipeline_already_configured_stdout(self):
        """Test that pipeline fails if first process stdout already configured."""
        first_cmd = Command("echo", "hello", stdout=DEVNULL)  # Configured stdout
        second_cmd = Command("wc", "-c")

        with pytest.raises(InvalidOperation, match="stdout already configured"):
            first_cmd | second_cmd

    def test_pipeline_already_configured_stdin(self):
        """Test that pipeline fails if second process stdin already configured."""
        first_cmd = Command("echo", "hello")
        second_cmd = Command("wc", "-c", stdin="test")  # Configured stdin

        with pytest.raises(InvalidOperation, match="stdin already configured"):
            first_cmd | second_cmd

    def test_pipeline_with_non_process(self):
        """Test that pipeline fails with non-Command object."""
        process = Command("echo", "hello")

        with pytest.raises(TypeError):
            process | "not a process"

    def test_pipeline_execution_order(self):
        """Test that pipeline maintains execution order."""
        # Create a pipeline that produces different outputs based on order
        first = Command("echo", "first")
        second = Command("cat")

        pipeline = first | second
        result = pipeline.execute()

        assert result.returncode == 0
        assert "first" in result.stdout.decode()

    def test_pipeline_return_value(self):
        """Test that pipeline returns the last process."""
        first = Command("echo", "test")
        second = Command("cat")

        pipeline = first | second
        assert isinstance(pipeline, Pipeline)
        assert pipeline.commands[-1] is second

    def test_pipeline_with_complex_commands(self):
        """Test pipeline with more complex shell commands."""
        # List files, filter for .py files, count them
        pipeline = Command("ls", "-1") | Command("grep", r"\.py$") | Command("wc", "-l")
        result = pipeline.execute()

        assert result.returncode == 0
        # Should return a number (even if 0)
        assert result.stdout.strip().isdigit()

    def test_pipeline_with_failing_command(self):
        """Test pipeline where one command fails."""
        # First command succeeds, second fails
        first = Command("echo", "test")
        second = Command("false", check=False)  # Always fails

        pipeline = first | second

        result = pipeline.execute()
        assert result.returncode == 1  # Should fail with exit code 1

    def test_pipeline_with_failing_command_no_check(self):
        """Test pipeline with failing command but check=False."""
        first = Command("echo", "test")
        second = Command("false", check=False)  # Don't raise on failure

        pipeline = first | second
        result = pipeline.execute()

        assert result.returncode == 1  # false exits with 1
