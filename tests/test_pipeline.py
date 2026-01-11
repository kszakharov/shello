"""Test pipeline functionality."""

import pytest

from shello import DEVNULL, Process, shell
from shello.exceptions import InvalidOperation, ProcessError


class TestPipeline:
    """Test cases for pipeline functionality."""

    def test_simple_pipeline(self):
        """Test simple pipeline: echo hello | wc -c."""
        echo_cmd = Process("echo", "hello")
        wc_cmd = Process("wc", "-c")

        pipeline = echo_cmd | wc_cmd
        result = pipeline.execute()

        # "hello" + newline = 6 characters
        assert result.returncode() == 0
        assert "6" in result.stdout_data()

    def test_pipeline_with_shell(self):
        """Test pipeline using shell factory."""
        pipeline = shell.echo("hello world") | shell.wc("-w")
        result = pipeline.execute()

        assert result.returncode() == 0
        assert "2" in result.stdout_data()  # "hello world" has 2 words

    def test_pipeline_stderr_capture(self):
        """Test pipeline stderr capture."""
        # Command that outputs to stderr, then pipe to another command
        first_cmd = Process("sh", "-c", "echo 'error' >&2; echo 'output'")
        second_cmd = Process("wc", "-c")

        pipeline = first_cmd | second_cmd
        result = pipeline.execute()

        assert result.returncode() == 0
        # wc -c counts characters, "output\n" is 7 characters
        assert "7" in result.stdout_data()
        # Pipeline stderr should contain stderr from first command
        assert "error" in result.stderr_data()

    def test_pipeline_chaining(self):
        """Test chaining multiple processes."""
        pipeline = (
            Process("echo", "a b c") | Process("tr", " ", "\n") | Process("wc", "-l")
        )
        result = pipeline.execute()

        assert result.returncode() == 0
        assert "3" in result.stdout_data()  # 3 lines

    def test_pipeline_with_stdin(self):
        """Test pipeline with stdin input to first process."""
        first_cmd = Process("wc", "-c", stdin="hello world")
        second_cmd = Process("tr", "-d", " ")

        pipeline = first_cmd | second_cmd
        result = pipeline.execute()

        assert result.returncode() == 0
        # Should remove spaces from the character count
        assert "11" in result.stdout_data() or "9" in result.stdout_data()

    def test_pipeline_already_configured_stdout(self):
        """Test that pipeline fails if first process stdout already configured."""
        first_cmd = Process("echo", "hello", stdout=DEVNULL)  # Configured stdout
        second_cmd = Process("wc", "-c")

        with pytest.raises(InvalidOperation, match="stdout already configured"):
            first_cmd | second_cmd

    def test_pipeline_already_configured_stdin(self):
        """Test that pipeline fails if second process stdin already configured."""
        first_cmd = Process("echo", "hello")
        second_cmd = Process("wc", "-c", stdin="test")  # Configured stdin

        with pytest.raises(InvalidOperation, match="stdin already configured"):
            first_cmd | second_cmd

    def test_pipeline_with_non_process(self):
        """Test that pipeline fails with non-Process object."""
        process = Process("echo", "hello")

        with pytest.raises(TypeError):
            process | "not a process"

    def test_pipeline_execution_order(self):
        """Test that pipeline maintains execution order."""
        # Create a pipeline that produces different outputs based on order
        first = Process("echo", "first")
        second = Process("cat")

        pipeline = first | second
        result = pipeline.execute()

        assert result.returncode() == 0
        assert "first" in result.stdout_data()

    def test_pipeline_return_value(self):
        """Test that pipeline returns the last process."""
        first = Process("echo", "test")
        second = Process("cat")

        pipeline = first | second
        assert pipeline is second
        assert isinstance(pipeline, Process)

    def test_pipeline_with_complex_commands(self):
        """Test pipeline with more complex shell commands."""
        # List files, filter for .py files, count them
        pipeline = Process("ls", "-1") | Process("grep", r"\.py$") | Process("wc", "-l")
        result = pipeline.execute()

        assert result.returncode() == 0
        # Should return a number (even if 0)
        assert result.stdout_data().strip().isdigit()

    def test_pipeline_with_failing_command(self):
        """Test pipeline where one command fails."""
        # First command succeeds, second fails
        first = Process("echo", "test")
        second = Process("false")  # Always fails

        pipeline = first | second

        with pytest.raises(ProcessError):  # Should raise error due to check=True
            pipeline.execute()

    def test_pipeline_with_failing_command_no_check(self):
        """Test pipeline with failing command but check=False."""
        first = Process("echo", "test")
        second = Process("false", check=False)  # Don't raise on failure

        pipeline = first | second
        result = pipeline.execute()

        assert result.returncode() == 1  # false exits with 1
