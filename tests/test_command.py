"""Test Command class."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest


from shello import Command, ANY_EXITCODE, STDOUT, Pipeline


def test_command_initialization_defaults():
    cmd = "echo"
    command = Command(cmd, "hello", "world")

    assert command.program == "echo"
    assert command.args == ("hello", "world")
    assert command.check is True
    assert command.ok_exitcodes == (0,)
    assert command.wait is True
    assert command.capture_stdout is True
    assert command.capture_stderr is True


def test_ok_exitcodes_normalization():
    # Integer should be converted to a tuple container
    cmd1 = Command("ls", ok_exitcodes=0)
    assert cmd1.ok_exitcodes == (0,)

    # Container (like range or list) should remain as-is
    cmd2 = Command("ls", ok_exitcodes=ANY_EXITCODE)
    assert cmd2.ok_exitcodes == ANY_EXITCODE


def test_pipe_operator():
    cmd1 = Command("echo", "hello")
    cmd2 = Command("grep", "hello")

    pipeline = cmd1 | cmd2

    # Verify it returns a Pipeline connecting the two commands
    assert isinstance(pipeline, Pipeline)
    # Assuming Pipeline stores commands in a list or attributes (adjust as per your Pipeline implementation)
    assert pipeline.commands == [cmd1, cmd2]


def test_pipe_operator_invalid():
    cmd = Command("echo", "hello")
    with pytest.raises(TypeError):
        cmd | "not a command"


def test_str_representation():
    # Basic command
    cmd = Command("python", "script.py")
    assert str(cmd) == "python script.py"

    # With redirection and timeout
    cmd_complex = Command(
        "cat",
        stdin=Path("input.txt"),
        stdout=Path("output.txt"),
        stderr=STDOUT,
        timeout=5.5,
    )
    expected = "cat < input.txt > output.txt 2>&1 [timeout: 5.5s]"
    assert str(cmd_complex) == expected


def test_repr_representation():
    cmd = Command("git", "status", "-s")
    assert repr(cmd) == "Command('git', 'status', '-s')"


@patch("shello.command.Process")
def test_execute(mock_process_class):
    mock_process_instance = MagicMock()
    mock_process_class.return_value = mock_process_instance

    cmd = Command("sleep", "1", wait=True)
    process = cmd.execute()

    # Verify Process was initialized with the command
    mock_process_class.assert_called_once_with(command=cmd)
    # Verify wait() was called since wait=True by default
    mock_process_instance.wait.assert_called_once()
    assert process == mock_process_instance


@patch("shello.command.Process")
def test_execute_no_wait(mock_process_class):
    mock_process_instance = MagicMock()
    mock_process_class.return_value = mock_process_instance

    cmd = Command("sleep", "1", wait=False)
    cmd.execute()

    mock_process_class.assert_called_once_with(command=cmd)
    # wait() should not be called if wait=False
    mock_process_instance.wait.assert_not_called()
