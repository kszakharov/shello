"""Shello - A modern Python library for shell-style process execution."""

from __future__ import annotations

from .exceptions import InvalidArgument, ProcessError, ShellError, TimeoutError
from .pipeline import Pipeline
from .process import ANY_EXITCODE, DEVNULL, STDOUT, Process
from .shell import Shell, binary_shell, shell

__all__ = [
    "binary_shell",
    "shell",
    "Shell",
    "Process",
    "ANY_EXITCODE",
    "DEVNULL",
    "STDOUT",
    "ShellError",
    "ProcessError",
    "InvalidArgument",
    "TimeoutError",
    "Pipeline",
]
