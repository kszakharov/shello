"""Shello - A modern Python library for shell-style process execution."""

from __future__ import annotations

from .exceptions import InvalidArgument, InvalidOperation, ProcessError, ShellError, TimeoutError, UnexpectedExitCodeError
from .pipeline import Pipeline
from .process import ANY_EXITCODE, DEVNULL, STDERR, STDOUT, Process
from .shell import Shell, binary_shell, shell

__all__ = [
    "binary_shell",
    "shell",
    "Shell",
    "Process",
    "ANY_EXITCODE",
    "DEVNULL",
    "STDERR",
    "STDOUT",
    "ShellError",
    "ProcessError",
    "InvalidArgument",
    "TimeoutError",
    "InvalidOperation",
    "UnexpectedExitCodeError",
    "Pipeline",
]
