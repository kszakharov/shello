"""Test Process class."""

import signal
import time

import pytest

from shello import DEVNULL, STDOUT, Process
from shello.exceptions import InvalidOperation, ProcessError, TimeoutError
from shello.process import ProcessState


class TestProcess:
    """Test cases for Process class."""

    def test_simple_command(self):
        """Test basic command execution."""
        process = Process("echo", "hello")
        result = process.execute()

        assert result.returncode == 0
        assert result.stdout.decode().strip() == "hello"
        assert result.stderr == b""

    def test_command_with_args(self):
        """Test command with multiple arguments."""
        process = Process("echo", "hello", "world")
        result = process.execute()

        assert result.returncode == 0
        assert result.stdout.decode().strip() == "hello world"

    def test_command_not_found(self):
        """Test handling of non-existent command."""
        process = Process("nonexistent_command_12345")

        with pytest.raises(ProcessError):
            process.execute()

    def test_nonzero_exit_code_no_check(self):
        """Test non-zero exit code with check=False."""
        process = Process("false", check=False)
        result = process.execute()

        assert result.returncode == 1
        assert result.stdout == b""
        assert result.stderr == b""

    def test_stderr_capture(self):
        """Test stderr capture."""
        # Command that outputs to stderr
        process = Process("sh", "-c", "echo 'error message' >&2")
        result = process.execute()

        assert result.returncode == 0
        assert result.stdout == b""
        assert result.stderr.decode().strip() == "error message"

    def test_stdin_string(self):
        """Test stdin with string input."""
        process = Process("wc", "-c", stdin=b"hello world")
        result = process.execute()

        assert result.returncode == 0
        # "hello world" has 11 characters
        assert "11" in result.stdout.decode()

    def test_devnull_stdin(self):
        """Test DEVNULL stdin (default)."""
        process = Process("wc", "-c", stdin=DEVNULL)
        with pytest.raises(ProcessError, match=f"Invalid file descriptor: {DEVNULL}"):
            process.execute()

        # Process should not have started
        assert process.state == ProcessState.SPAWNING

    def test_devnull_stdout(self):
        """Test DEVNULL stdout."""
        process = Process("echo", "hello", stdout=DEVNULL)
        result = process.execute()

        assert result.returncode == 0
        assert result.stdout == b""

    def test_stderr_to_stdout(self):
        """Test redirecting stderr to stdout."""
        process = Process("sh", "-c", "echo 'error' >&2", stderr=STDOUT)
        result = process.execute()

        assert result.returncode == 0
        assert "error" in result.stdout.decode()
        assert result.stderr == b""

    def test_process_attributes(self):
        """Test process attributes and methods."""
        process = Process("echo", "test")

        # Before execution
        assert process.state == ProcessState.PENDING
        assert process.pid is None

        process.execute()

        # After execution
        assert process.state == ProcessState.TERMINATED
        assert process.returncode == 0
        assert process.pid is not None
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
        """Test wait without execution raises error."""
        process = Process("echo", "test")

        with pytest.raises(InvalidOperation):
            process.wait()

    def test_stdout_before_execution(self):
        """Test accessing stdout before execution raises error."""
        process = Process("echo", "test")

        with pytest.raises(InvalidOperation, match="not executed"):
            _ = process.stdout

    def test_invalid_stdin_type(self):
        """Test invalid stdin type raises error."""
        process = Process("echo", stdin=12345)

        with pytest.raises(ProcessError, match="Invalid file descriptor: 12345"):
            process.execute()

    def test_working_directory(self, tmp_path):
        """Test running process in specific working directory."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        # Run ls in temp directory
        process = Process("ls", cwd=tmp_path)
        result = process.execute()

        assert result.returncode == 0
        assert "test.txt" in result.stdout.decode()

    def test_environment_variables(self):
        """Test setting environment variables."""
        process = Process("sh", "-c", "echo $TEST_VAR", env={"TEST_VAR": "test_value"})
        result = process.execute()

        assert result.returncode == 0
        assert result.stdout.decode().strip() == "test_value"

    def test_timeout_no_timeout(self):
        """Test timeout parameter when process completes within timeout."""
        process = Process("echo", "hello", timeout=10.0)
        result = process.execute()

        assert result.returncode == 0
        assert result.stdout.decode().strip() == "hello"

    def test_timeout_exceeded(self):
        """Test timeout when process exceeds timeout limit."""
        process = Process("sleep", "2", timeout=0.1, ok_exitcodes=[-signal.SIGKILL])

        with pytest.raises(TimeoutError):
            process.execute()

        # Process should be terminated
        assert process.state == ProcessState.TERMINATED
        # Output should be empty for sleep command
        assert process.stdout == b""
        assert process.stderr == b""

    def test_timeout_none(self):
        """Test that timeout=None means no timeout (default behavior)."""
        process = Process("sleep", "0.1", timeout=None)
        result = process.execute()

        assert result.returncode == 0
        assert result.execution_time >= 0.1  # Should have waited

    def test_pipeline_timeout_source(self):
        """Test timeout on the source process in a pipeline."""
        pipeline = Process("sleep", "2", timeout=0.5) | Process("echo", "done")
        pipeline.execute()
        assert pipeline.processes[0].state == ProcessState.TERMINATED
        assert pipeline.processes[0].returncode == -signal.SIGKILL

    def test_pipeline_timeout_sink(self):
        """Test timeout on the sink process in a pipeline."""
        pipeline = Process("echo", "hello") | Process("sleep", "2", timeout=0.5, ok_exitcodes=[-signal.SIGKILL])
        with pytest.raises(TimeoutError):
            pipeline.execute()

    def test_binary_mode_timeout(self):
        """Test timeout in binary mode."""
        script = "import sys, time; sys.stdout.buffer.write(b'hello'); time.sleep(2)"
        process = Process("python3", "-c", script, text=False, timeout=0.5, ok_exitcodes=[-signal.SIGKILL])
        with pytest.raises(TimeoutError):
            process.execute()
        # In current implementation, output is empty on timeout
        assert process.stdout == b""

    def test_custom_exit_codes_timeout(self):
        """Test that timeout takes precedence over custom exit codes."""
        process = Process("sleep", "2", ok_exitcodes=[-signal.SIGKILL], timeout=0.5)
        with pytest.raises(TimeoutError):  # Should raise TimeoutError, not ProcessError
            process.execute()

    def test_very_short_timeout(self):
        """Test extremely short timeout causes TimeoutError."""
        process = Process("sleep", "0.01", timeout=0.001, ok_exitcodes=[-signal.SIGKILL])
        with pytest.raises(TimeoutError):
            process.execute()

    def test_timeout_race_condition(self):
        """Test timeout with very fast process."""
        start = time.time()
        process = Process("echo", "test", timeout=0.01)
        result = process.execute()
        elapsed = time.time() - start
        assert result.returncode == 0
        assert elapsed < 0.1  # Should complete quickly


def test_binary_mode():
    """Test binary mode execution."""
    process = Process("echo", "hello", text=False)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stdout, bytes)
    assert b"hello" in result.stdout


def test_text_mode_stdout_is_str():
    """Test that text=True yields str stdout at runtime."""
    process = Process("echo", "hello", text=True)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stdout, str), f"Expected str, got {type(result.stdout)}"
    assert "hello" in result.stdout


def test_text_mode_stderr_is_str():
    """Test that text=True yields str stderr at runtime."""
    process = Process("sh", "-c", "echo err >&2", text=True)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stderr, str), f"Expected str, got {type(result.stderr)}"
    assert "err" in result.stderr


def test_binary_mode_stdout_is_bytes():
    """Test that text=False (default) yields bytes stdout at runtime."""
    process = Process("echo", "hello", text=False)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stdout, bytes), f"Expected bytes, got {type(result.stdout)}"
    assert b"hello" in result.stdout


def test_binary_mode_stderr_is_bytes():
    """Test that text=False (default) yields bytes stderr at runtime."""
    process = Process("sh", "-c", "echo err >&2", text=False)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stderr, bytes), f"Expected bytes, got {type(result.stderr)}"
    assert b"err" in result.stderr


def test_binary_mode_capture_and_print_stdout():
    """Test bytes mode with capture_stdout+print_stdout uses bytes join (not str join)."""
    process = Process("echo", "hello", text=False, capture_stdout=True, print_stdout=True)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stdout, bytes), f"Expected bytes, got {type(result.stdout)}"
    assert b"hello" in result.stdout


def test_binary_mode_capture_and_print_stderr():
    """Test bytes mode with capture_stderr+print_stderr uses bytes join (not str join)."""
    process = Process("sh", "-c", "echo err >&2", text=False, capture_stderr=True, print_stderr=True)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stderr, bytes), f"Expected bytes, got {type(result.stderr)}"
    assert b"err" in result.stderr


def test_text_mode_stdout_is_str_when_no_output():
    """Test that stdout fallback is str in text mode when no output is captured."""
    process = Process("true", text=True, capture_stdout=False)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stdout, str), f"Expected str fallback, got {type(result.stdout)}"
    assert result.stdout == ""


def test_binary_mode_stdout_is_bytes_when_no_output():
    """Test that stdout fallback is bytes in binary mode when no output is captured."""
    process = Process("true", text=False, capture_stdout=False)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stdout, bytes), f"Expected bytes fallback, got {type(result.stdout)}"
    assert result.stdout == b""


def test_text_mode_capture_and_print_stdout():
    """Test text mode with capture_stdout+print_stdout uses str join (not bytes join)."""
    process = Process("echo", "hello", text=True, capture_stdout=True, print_stdout=True)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stdout, str), f"Expected str, got {type(result.stdout)}"
    assert "hello" in result.stdout


def test_text_mode_capture_and_print_stderr():
    """Test text mode with capture_stderr+print_stderr uses str join (not bytes join)."""
    process = Process("sh", "-c", "echo err >&2", text=True, capture_stderr=True, print_stderr=True)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stderr, str), f"Expected str, got {type(result.stderr)}"
    assert "err" in result.stderr


def test_text_mode_stderr_is_str_when_no_output():
    """Test that stderr fallback is str in text mode when stderr is not captured."""
    process = Process("true", text=True, capture_stderr=False)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stderr, str), f"Expected str fallback, got {type(result.stderr)}"
    assert result.stderr == ""


def test_binary_mode_stderr_is_bytes_when_no_output():
    """Test that stderr fallback is bytes in binary mode when stderr is not captured."""
    process = Process("true", text=False, capture_stderr=False)
    result = process.execute()

    assert result.returncode == 0
    assert isinstance(result.stderr, bytes), f"Expected bytes fallback, got {type(result.stderr)}"
    assert result.stderr == b""


