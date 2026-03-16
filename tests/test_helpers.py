"""Tests for shello/helpers.py."""

import os
import tempfile

import pytest

from shello.exceptions import InvalidArgument
from shello.helpers import check_fd


class TestCheckFd:
    """Tests for check_fd()."""

    def test_valid_readable_fd_with_mode_r(self):
        """A readable fd with mode 'r' should not raise."""
        with tempfile.TemporaryFile() as f:
            check_fd(f.fileno(), "r")

    def test_valid_writable_fd_with_mode_w(self):
        """A writable fd with mode 'w' should not raise."""
        with tempfile.TemporaryFile(mode="wb") as f:
            check_fd(f.fileno(), "w")

    def test_valid_write_only_fd_with_mode_w(self):
        """An O_WRONLY fd (pipe write end) with mode 'w' should not raise."""
        r_fd, w_fd = os.pipe()
        try:
            check_fd(w_fd, "w")
        finally:
            os.close(r_fd)
            os.close(w_fd)

    def test_valid_rdwr_fd_with_mode_rw(self):
        """An O_RDWR fd with mode 'rw' should not raise."""
        with tempfile.TemporaryFile() as f:
            check_fd(f.fileno(), "rw")

    def test_invalid_mode_raises_value_error(self):
        """An unrecognized mode string should raise ValueError."""
        with tempfile.TemporaryFile() as f:
            with pytest.raises(ValueError, match="Invalid mode"):
                check_fd(f.fileno(), "x")

    def test_write_only_fd_with_mode_r_raises_invalid_argument(self):
        """A write-only fd with mode 'r' should raise InvalidArgument."""
        r_fd, w_fd = os.pipe()
        try:
            with pytest.raises(InvalidArgument):
                check_fd(w_fd, "r")
        finally:
            os.close(r_fd)
            os.close(w_fd)

    def test_read_only_fd_with_mode_w_raises_invalid_argument(self):
        """A read-only fd with mode 'w' should raise InvalidArgument."""
        r_fd, w_fd = os.pipe()
        try:
            with pytest.raises(InvalidArgument):
                check_fd(r_fd, "w")
        finally:
            os.close(r_fd)
            os.close(w_fd)

    def test_read_only_fd_with_mode_rw_raises_invalid_argument(self):
        """A read-only fd (pipe read end) with mode 'rw' should raise InvalidArgument."""
        r_fd, w_fd = os.pipe()
        try:
            with pytest.raises(InvalidArgument):
                check_fd(r_fd, "rw")
        finally:
            os.close(r_fd)
            os.close(w_fd)

    def test_invalid_fd_raises_invalid_argument(self):
        """An invalid (closed) fd should raise InvalidArgument."""
        r_fd, w_fd = os.pipe()
        os.close(r_fd)
        os.close(w_fd)
        with pytest.raises(InvalidArgument):
            check_fd(w_fd, "w")
