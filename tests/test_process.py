"""Test Process class."""

import os
import signal
import time
from pathlib import Path

import pytest

from shello import DEVNULL, STDERR, STDOUT, InvalidArgument, InvalidOperation, Process, UnexpectedExitCodeError
from shello.exceptions import ProcessError, TimeoutError
from shello.interactive import InteractiveProcess
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
        assert process.state == ProcessState.PENDING

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
        assert result.execution_time is not None
        assert result.execution_time >= 0.1  # Should have waited

    def test_pipeline_timeout_source(self):
        """Test timeout on the source process in a pipeline."""
        pipeline = Process("sleep", "2", timeout=0.5) | Process("echo", "done")
        with pytest.raises(TimeoutError):
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


def test_unexpected_exit_code_error_check_true():
    """Test UnexpectedExitCodeError raised when check=True and process exits non-zero."""
    process = Process("false", check=True)

    with pytest.raises(UnexpectedExitCodeError):
        process.execute()


def test_check_returncode_raises_for_nonzero():
    """Test check_returncode() raises UnexpectedExitCodeError for non-zero exit."""
    process = Process("false", check=False)
    process.execute()

    with pytest.raises(UnexpectedExitCodeError):
        process.check_returncode()


def test_check_returncode_does_not_raise_when_code_in_ok_exitcodes():
    """Test check_returncode() does not raise when exit code is in ok_exitcodes."""
    process = Process("sh", "-c", "exit 2", ok_exitcodes=2, check=False)
    process.execute()
    process.check_returncode()  # Should not raise


def test_stderr_before_execution_raises():
    """Test accessing .stderr before execute() raises InvalidOperation."""
    process = Process("echo", "test")

    with pytest.raises(InvalidOperation):
        _ = process.stderr


def test_returncode_before_execution_raises():
    """Test accessing .returncode before execute() raises InvalidOperation."""
    process = Process("echo", "test")

    with pytest.raises(InvalidOperation):
        _ = process.returncode


def test_wait_false_then_explicit_wait():
    """Test wait=False allows deferring wait, then explicit .wait() completes successfully."""
    process = Process("sh", "-c", "sleep 0.05 && echo hello", wait=False)
    process.execute()

    # Process is not yet terminated immediately after execute() with wait=False
    assert process.state != ProcessState.TERMINATED

    result = process.wait()

    assert result.returncode == 0
    assert b"hello" in result.stdout


def test_stderr_constant_str_representation():
    """Test that stdout=STDERR produces 1>&2 in str()."""
    process = Process("echo", "hi", stdout=STDERR)
    assert "1>&2" in str(process)


def test_stderr_constant_stdout_not_captured():
    """Test that stdout=STDERR routes stdout to fd 2, so process.stdout is empty.

    When stdout=STDERR, stdout goes to the parent's fd 2 (terminal stderr),
    not to a capture pipe. So captured stdout should be empty.
    """
    process = Process(
        "echo",
        "hello",
        stdout=STDERR,
        capture_stdout=False,
        capture_stderr=True,
    )
    process.execute()
    # stdout was redirected to fd 2, not captured
    assert process.stdout == b""


def test_stderr_constant_is_exported_from_shello():
    """Test that STDERR is importable from shello."""
    import shello

    assert hasattr(shello, "STDERR")
    assert shello.STDERR is STDERR


def test_context_manager_returns_process():
    """Test that `with Process(...) as p:` yields the process instance."""
    with Process("echo", "hello") as p:
        assert isinstance(p, Process)
        result = p.execute()
    assert result.returncode == 0


def test_context_manager_result_accessible_inside_block():
    """Test that execute() result is accessible inside the with block."""
    with Process("echo", "world") as p:
        result = p.execute()
        assert b"world" in result.stdout


def test_context_manager_kills_running_background_process():
    """Test that a running background process is killed on context exit."""
    with Process("sleep", "10", wait=False, check=False) as p:
        p.execute()
        assert p.state in {ProcessState.RUNNING, ProcessState.SPAWNING}
    # After exiting the context, the process should have been killed
    p.wait()
    assert p.state == ProcessState.TERMINATED
    assert p.returncode != 0


def test_context_manager_no_kill_when_not_started():
    """Test that __exit__ does not raise when process was never executed."""
    with Process("echo", "hi") as p:
        pass  # Never called execute()
    # No exception should be raised; process stays PENDING
    assert p.state == ProcessState.PENDING


def test_context_manager_no_kill_when_already_terminated():
    """Test that __exit__ does not raise when process already terminated."""
    with Process("echo", "hi") as p:
        p.execute()
    # Process is TERMINATED; kill() should not be called (would raise InvalidOperation)
    assert p.state == ProcessState.TERMINATED


class TestInteractiveMode:
    """Tests for interactive=True parameter."""

    def test_interactive_simple_command_completes(self):
        """Test that interactive=True executes a simple command and completes successfully."""
        process = Process("true", interactive=True)
        result = process.execute()

        assert result.returncode == 0
        assert result.state == ProcessState.TERMINATED

    def test_interactive_wait_false_then_wait(self):
        """Test that interactive=True with wait=False is non-blocking and can be waited on."""
        process = Process("sh", "-c", "sleep 0.05", interactive=True, wait=False)
        process.execute()

        # Process must not be terminated immediately after non-blocking execute()
        assert process.state != ProcessState.TERMINATED

        result = process.wait()
        assert result.returncode == 0
        assert result.state == ProcessState.TERMINATED

    def test_interactive_stdin_bytes_raises(self):
        """Test that interactive=True with stdin=bytes raises InvalidArgument at construction."""
        with pytest.raises(InvalidArgument):
            Process("cat", interactive=True, stdin=b"data")

    def test_interactive_stdin_str_raises(self):
        """Test that interactive=True with stdin=str raises InvalidArgument at construction."""
        with pytest.raises(InvalidArgument):
            Process("cat", interactive=True, stdin="data")  # type: ignore[arg-type]

    def test_interactive_stdin_path_raises(self):
        """Test that interactive=True with stdin=Path raises InvalidArgument at construction."""
        with pytest.raises(InvalidArgument):
            Process("cat", interactive=True, stdin=Path("/dev/null"))

    def test_interactive_stdin_fd_raises(self):
        """Test that interactive=True with stdin as int fd raises InvalidArgument at construction."""
        with pytest.raises(InvalidArgument):
            Process("cat", interactive=True, stdin=0)  # 0 is stdin fd

    def test_interactive_stdout_is_empty_bytes(self):
        """Test that interactive=True leaves stdout as empty bytes after execution."""
        process = Process("true", interactive=True)
        process.execute()

        assert process.stdout == b""

    def test_interactive_stderr_is_empty_bytes(self):
        """Test that interactive=True leaves stderr as empty bytes after execution."""
        process = Process("true", interactive=True)
        process.execute()

        assert process.stderr == b""

    def test_interactive_correct_returncode_success(self):
        """Test that interactive=True process returns correct returncode on success."""
        process = Process("true", interactive=True)
        process.execute()

        assert process.returncode == 0

    def test_interactive_correct_returncode_failure(self):
        """Test that interactive=True process returns correct returncode on failure."""
        process = Process("false", interactive=True, check=False)
        process.execute()

        assert process.returncode == 1

    def test_interactive_text_mode_stdout_is_empty_str(self):
        """Test that interactive=True with text=True leaves stdout as empty str after execution."""
        process = Process("true", interactive=True, text=True)
        process.execute()

        assert process.stdout == ""
        assert isinstance(process.stdout, str)


class TestInteractiveProcessBasic:
    """Basic tests for InteractiveProcess (PTY-based)."""

    def test_pty_simple_command_completes(self):
        """Test that InteractiveProcess executes a simple command and completes."""
        process = InteractiveProcess("true")
        result = process.execute()

        assert result.returncode == 0
        assert result.state == ProcessState.TERMINATED

    def test_pty_failure_returncode(self):
        """Test that InteractiveProcess returns correct returncode on failure."""
        process = InteractiveProcess("false", check=False)
        process.execute()

        assert process.returncode == 1

    def test_pty_wait_false_then_wait(self):
        """Test that InteractiveProcess with wait=False is non-blocking."""
        process = InteractiveProcess("sh", "-c", "sleep 0.05", wait=False)
        process.execute()

        assert process.state != ProcessState.TERMINATED

        result = process.wait()
        assert result.returncode == 0
        assert result.state == ProcessState.TERMINATED

    def test_pty_pid_is_set(self):
        """Test that InteractiveProcess sets pid after execute."""
        process = InteractiveProcess("true")
        process.execute()

        assert process.pid is not None
        assert isinstance(process.pid, int)

    def test_pty_returncode_before_execution_raises(self):
        """Test that accessing returncode before execute raises InvalidOperation."""
        process = InteractiveProcess("true")

        with pytest.raises(InvalidOperation):
            _ = process.returncode

    def test_pty_kill_unexecuted_raises(self):
        """Test that killing unexecuted InteractiveProcess raises InvalidOperation."""
        process = InteractiveProcess("sleep", "10")

        with pytest.raises(InvalidOperation, match="not executed"):
            process.kill()

    def test_interactive_pty_env(self):
        """Test that InteractiveProcess passes env vars to the child process."""
        # sh -c 'test -n "$TEST_VAR"' exits 0 if TEST_VAR is non-empty
        process = InteractiveProcess(
            "sh",
            "-c",
            'test -n "$TEST_VAR"',
            env={"TEST_VAR": "hello", "PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
        result = process.execute()

        assert result.returncode == 0

    def test_interactive_pty_cwd(self):
        """Test that InteractiveProcess respects the cwd parameter."""
        # pwd exits 0 regardless; we just verify successful execution with cwd set
        process = InteractiveProcess("pwd", cwd="/tmp")
        result = process.execute()

        assert result.returncode == 0

    def test_interactive_kill(self):
        """Test that InteractiveProcess can be killed and returns a signal-based returncode."""
        process = InteractiveProcess("sleep", "10", wait=False, check=False)
        process.execute()

        assert process.state != ProcessState.TERMINATED

        process.kill(signal.SIGTERM)
        result = process.wait()

        assert result.state == ProcessState.TERMINATED
        assert result.returncode == -signal.SIGTERM

    def test_execute_twice_raises(self):
        """Test that calling execute() twice raises InvalidOperation."""
        process = InteractiveProcess("true")
        process.execute()

        with pytest.raises(InvalidOperation):
            process.execute()

    def test_wait_without_execute_raises(self):
        """Test that calling wait() without execute() raises InvalidOperation."""
        process = InteractiveProcess("true")

        with pytest.raises(InvalidOperation, match="not started"):
            process.wait()

    def test_pty_stdout_raises(self):
        """Test that accessing stdout on InteractiveProcess raises InvalidOperation."""
        process = InteractiveProcess("true")
        process.execute()

        with pytest.raises(InvalidOperation, match="not captured"):
            _ = process.stdout

    def test_pty_stderr_raises(self):
        """Test that accessing stderr on InteractiveProcess raises InvalidOperation."""
        process = InteractiveProcess("true")
        process.execute()

        with pytest.raises(InvalidOperation, match="not captured"):
            _ = process.stderr


class TestProcessStrRepr:
    """Test __str__ and __repr__ representations."""

    def test_stderr_repr(self):
        """Test that STDERR sentinel has a readable repr."""
        assert repr(STDERR) == "STDERR"

    def test_str_with_stdin_path(self):
        """Test __str__ includes stdin path redirection."""
        p = Process("cat", stdin=Path("/tmp/foo"))
        s = str(p)
        assert "< /tmp/foo" in s

    def test_str_with_stdout_devnull(self):
        """Test __str__ includes stdout devnull redirection."""
        p = Process("echo", stdout=DEVNULL)
        s = str(p)
        assert "> /dev/null" in s

    def test_str_with_timeout(self):
        """Test __str__ includes timeout info."""
        p = Process("echo", timeout=5)
        s = str(p)
        assert "[timeout: 5s]" in s
