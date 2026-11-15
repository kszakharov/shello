"""Test Process class."""

import signal
import time

import pytest

from shello import DEVNULL, STDOUT, Command
from shello.exceptions import InvalidOperation, ProcessError, TimeoutError
from shello.process import ProcessState


class TestProcess:
    """Test cases for Command class."""

    def test_simple_command(self):
        """Test basic command execution."""
        command = Command("echo", "hello")
        process = command.execute()

        assert process.returncode == 0
        assert process.stdout.decode().strip() == "hello"
        assert process.stderr == ""

    def test_command_with_args(self):
        """Test command with multiple arguments."""
        command = Command("echo", "hello", "world")
        process = command.execute()

        assert process.returncode == 0
        assert process.stdout.decode().strip() == "hello world"

    def test_command_not_found(self):
        """Test handling of non-existent command."""
        command = Command("nonexistent_command_12345")

        with pytest.raises(ProcessError):
            command.execute()

    def test_nonzero_exit_code_no_check(self):
        """Test non-zero exit code with check=False."""
        command = Command("false", check=False)
        process = command.execute()

        assert process.returncode == 1
        assert process.stdout == ""
        assert process.stderr == ""

    def test_stderr_capture(self):
        """Test stderr capture."""
        # Command that outputs to stderr
        command = Command("sh", "-c", "echo 'error message' >&2")
        process = command.execute()

        assert process.returncode == 0
        assert process.stdout == ""
        assert process.stderr.decode().strip() == "error message"

    def test_stdin_string(self):
        """Test stdin with string input."""
        command = Command("wc", "-c", stdin=b"hello world")
        process = command.execute()

        assert process.returncode == 0
        # "hello world" has 11 characters
        assert "11" in process.stdout.decode()

    def test_devnull_stdin(self):
        """Test DEVNULL stdin (default)."""
        command = Command("wc", "-c", stdin=DEVNULL)
        with pytest.raises(ProcessError, match=f"Invalid file descriptor: {DEVNULL}"):
            command.execute()

    def test_devnull_stdout(self):
        """Test DEVNULL stdout."""
        command = Command("echo", "hello", stdout=DEVNULL)
        process = command.execute()

        assert process.returncode == 0
        assert process.stdout == ""

    def test_stderr_to_stdout(self):
        """Test redirecting stderr to stdout."""
        command = Command("sh", "-c", "echo 'error' >&2", stderr=STDOUT)
        process = command.execute()

        assert process.returncode == 0
        assert "error" in process.stdout.decode()
        assert process.stderr == ""

    def test_process_attributes(self):
        """Test command attributes and methods."""
        command = Command("echo", "test")
        process = command.execute()

        # After execution
        assert process.state == ProcessState.TERMINATED
        assert process.returncode == 0
        assert process.pid is not None
        assert str(process.command) == "echo test"
        assert "Process" in repr(process)

    def test_double_execution_error(self):
        """Test that executing same command twice raises error."""
        command = Command("echo", "hello")
        process = command.execute()

        with pytest.raises(InvalidOperation, match="already executed"):
            process.execute()

    def test_invalid_stdin_type(self):
        """Test invalid stdin type raises error."""
        command = Command("echo", stdin=12345)

        with pytest.raises(ProcessError, match="Invalid file descriptor: 12345"):
            command.execute()

    def test_working_directory(self, tmp_path):
        """Test running command in specific working directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        # Run ls in temp directory
        command = Command("ls", cwd=tmp_path)
        process = command.execute()

        assert process.returncode == 0
        assert "test.txt" in process.stdout.decode()

    def test_environment_variables(self):
        """Test setting environment variables."""
        command = Command("sh", "-c", "echo $TEST_VAR", env={"TEST_VAR": "test_value"})
        process = command.execute()

        assert process.returncode == 0
        assert process.stdout.decode().strip() == "test_value"

    def test_timeout_no_timeout(self):
        """Test timeout parameter when command completes within timeout."""
        command = Command("echo", "hello", timeout=10.0)
        process = command.execute()

        assert process.returncode == 0
        assert process.stdout.decode().strip() == "hello"

    def test_timeout_exceeded(self):
        """Test timeout when command exceeds timeout limit."""
        command = Command("sleep", "2", timeout=0.1, ok_exitcodes=[-signal.SIGKILL], wait=False)
        process = command.execute()

        with pytest.raises(TimeoutError):
            process.wait()

        # Command should be terminated
        assert process.state == ProcessState.TERMINATED
        # Output should be empty for sleep command
        assert process.stdout == ""
        assert process.stderr == ""

    def test_timeout_none(self):
        """Test that timeout=None means no timeout (default behavior)."""
        command = Command("sleep", "0.1", timeout=None)
        process = command.execute()

        assert process.returncode == 0
        assert process.execution_time >= 0.1  # Should have waited

    def test_pipeline_timeout_source(self):
        """Test timeout on the source command in a pipeline."""
        pipeline = Command("sleep", "2", timeout=0.5) | Command("echo", "done")
        pipeline.execute()
        assert pipeline.processes[0].state == ProcessState.TERMINATED
        assert pipeline.processes[0].returncode == -signal.SIGKILL

    def test_pipeline_timeout_sink(self):
        """Test timeout on the sink command in a pipeline."""
        pipeline = Command("echo", "hello") | Command("sleep", "2", timeout=0.5, ok_exitcodes=[-signal.SIGKILL])
        with pytest.raises(TimeoutError):
            pipeline.execute()

    def test_binary_mode_timeout(self):
        """Test timeout in binary mode."""
        script = "import sys, time; sys.stdout.buffer.write(b'hello'); time.sleep(2)"
        command = Command("python3", "-c", script, text=False, timeout=0.5, ok_exitcodes=[-signal.SIGKILL], wait=False)
        process = command.execute()
        with pytest.raises(TimeoutError):
            process.wait()
        # In current implementation, output is empty on timeout
        assert process.stdout == ""

    def test_custom_exit_codes_timeout(self):
        """Test that timeout takes precedence over custom exit codes."""
        command = Command("sleep", "2", ok_exitcodes=[-signal.SIGKILL], timeout=0.5)
        with pytest.raises(TimeoutError):  # Should raise TimeoutError, not ProcessError
            command.execute()

    def test_very_short_timeout(self):
        """Test extremely short timeout causes TimeoutError."""
        command = Command("sleep", "0.01", timeout=0.001, ok_exitcodes=[-signal.SIGKILL])
        with pytest.raises(TimeoutError):
            command.execute()

    def test_timeout_race_condition(self):
        """Test timeout with very fast command."""
        start = time.time()
        command = Command("echo", "test", timeout=0.01)
        process = command.execute()
        elapsed = time.time() - start
        assert process.returncode == 0
        assert elapsed < 0.1  # Should complete quickly


def test_binary_mode():
    """Test binary mode execution."""
    command = Command("echo", "hello", text=False)
    process = command.execute()

    assert process.returncode == 0
    # In binary mode, check that hello appears in output
    output = process.stdout
    # In binary mode, stdout may be bytes or str depending on implementation
    if type(output) is bytes:
        assert b"hello" in output
    else:
        assert "hello" in output

    def test_output_truncation(self):
        """Test output size limit and truncation."""
        # Create a command that generates large output
        large_process = Command("python3", "-c", "print('x' * 10000)", max_output_size=1000)
        process = large_process.execute()

        # Output should be truncated
        assert len(process.stdout()) <= 1100  # 1000 + truncation message
        assert "[OUTPUT TRUNCATED]" in process.stdout()

        # Small output should not be truncated
        small_process = Command("echo", "hello", max_output_size=1000)
        small_result = small_process.execute()
        assert small_result.stdout() == "hello\n"
