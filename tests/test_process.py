"""Test Process class."""

import pytest

from shello import DEVNULL, STDOUT, Process
from shello.exceptions import InvalidArgument, InvalidOperation, ProcessError


class TestProcess:
    """Test cases for Process class."""

    def test_simple_command(self):
        """Test basic command execution."""
        process = Process("echo", "hello")
        result = process.execute()

        assert result.returncode() == 0
        assert result.stdout_data().strip() == "hello"
        assert result.stderr_data() == ""

    def test_command_with_args(self):
        """Test command with multiple arguments."""
        process = Process("echo", "hello", "world")
        result = process.execute()

        assert result.returncode() == 0
        assert result.stdout_data().strip() == "hello world"

    def test_command_not_found(self):
        """Test handling of non-existent command."""
        process = Process("nonexistent_command_12345")

        with pytest.raises(ProcessError) as exc_info:
            process.execute()

        assert exc_info.value.exit_code == 127
        assert "Command not found" in str(exc_info.value)

    def test_nonzero_exit_code(self):
        """Test handling of non-zero exit codes."""
        # Using false command which always exits with 1
        process = Process("false")

        with pytest.raises(ProcessError) as exc_info:
            process.execute()

        assert exc_info.value.exit_code == 1

    def test_nonzero_exit_code_no_check(self):
        """Test non-zero exit code with check=False."""
        process = Process("false", check=False)
        result = process.execute()

        assert result.returncode() == 1
        assert result.stdout_data() == ""
        assert result.stderr_data() == ""

    def test_stderr_capture(self):
        """Test stderr capture."""
        # Command that outputs to stderr
        process = Process("sh", "-c", "echo 'error message' >&2")
        result = process.execute()

        assert result.returncode() == 0
        assert result.stdout_data() == ""
        assert result.stderr_data().strip() == "error message"

    def test_stdin_string(self):
        """Test stdin with string input."""
        process = Process("wc", "-c", stdin="hello world")
        result = process.execute()

        assert result.returncode() == 0
        # "hello world" has 11 characters
        assert "11" in result.stdout_data()

    def test_devnull_stdin(self):
        """Test DEVNULL stdin (default)."""
        process = Process("wc", "-c", stdin=DEVNULL)
        result = process.execute()

        assert result.returncode() == 0
        assert "0" in result.stdout_data()

    def test_devnull_stdout(self):
        """Test DEVNULL stdout."""
        process = Process("echo", "hello", stdout=DEVNULL)
        result = process.execute()

        assert result.returncode() == 0
        assert result.stdout_data() == ""

    def test_stderr_to_stdout(self):
        """Test redirecting stderr to stdout."""
        process = Process("sh", "-c", "echo 'error' >&2", stderr=STDOUT)
        result = process.execute()

        assert result.returncode() == 0
        assert "error" in result.stdout_data()
        assert result.stderr_data() == ""

    def test_process_attributes(self):
        """Test process attributes and methods."""
        process = Process("echo", "test")

        # Before execution
        assert not process._executed
        assert process.pid() is None

        process.execute()

        # After execution
        assert process._executed
        assert process.returncode() == 0
        assert process.pid() is not None
        assert str(process) == "echo test"
        assert "Process" in repr(process)

    def test_double_execution_error(self):
        """Test that executing same process twice raises error."""
        process = Process("echo", "hello")
        process.execute()

        with pytest.raises(InvalidOperation, match="already executed"):
            process.execute()

    def test_kill_unexecuted_process(self):
        """Test killing unexecuted process raises error."""
        process = Process("sleep", "1")

        with pytest.raises(InvalidOperation, match="not executed"):
            process.kill()

    def test_wait_without_execution(self):
        """Test wait without execution auto-executes."""
        process = Process("echo", "test")
        exit_code = process.wait()

        assert exit_code == 0
        assert process._executed

    def test_stdout_data_before_execution(self):
        """Test accessing stdout_data before execution raises error."""
        process = Process("echo", "test")

        with pytest.raises(InvalidOperation, match="not executed"):
            process.stdout_data()

    def test_invalid_stdin_type(self):
        """Test invalid stdin type raises error."""
        process = Process("echo", stdin=12345)  # invalid type

        with pytest.raises(InvalidArgument):
            process.execute()

    def test_working_directory(self, tmp_path):
        """Test running process in specific working directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        # Run ls in temp directory
        process = Process("ls", cwd=tmp_path)
        result = process.execute()

        assert result.returncode() == 0
        assert "test.txt" in result.stdout_data()

    def test_environment_variables(self):
        """Test setting environment variables."""
        process = Process("sh", "-c", "echo $TEST_VAR", env={"TEST_VAR": "test_value"})
        result = process.execute()

        assert result.returncode() == 0
        assert result.stdout_data().strip() == "test_value"


def test_binary_mode():
    """Test binary mode execution."""
    process = Process("echo", "hello", text=False)
    result = process.execute()

    assert result.returncode() == 0
    # In binary mode, check that hello appears in output
    output = result.stdout_data()
    # In binary mode, stdout_data may be bytes or str depending on implementation
    if type(output) is bytes:
        assert b"hello" in output
    else:
        assert "hello" in output
