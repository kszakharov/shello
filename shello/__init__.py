"""Shello - A modern Python library for shell-style process execution."""

from __future__ import annotations

from .exceptions import InvalidArgument, ProcessError, ShellError
from .process import DEVNULL, STDERR, STDOUT, Process
from .shell import Shell

__all__ = [
    "Shell",
    "Process",
    "DEVNULL",
    "STDOUT",
    "STDERR",
    "ShellError",
    "ProcessError",
    "InvalidArgument",
]

# Default shell instance
shell = Shell()
