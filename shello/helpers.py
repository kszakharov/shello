import fcntl
import os

from .exceptions import InvalidArgument
from .types import FileDescriptorLike


def check_fd(fd: FileDescriptorLike, mode: str) -> None:
    """Check if a file descriptor is valid and has the required mode.

    Args:
        fd: File descriptor to check.
        mode: Mode to check ('r' for read, 'w' for write, 'rw' for read-write).
    Raises:
        InvalidArgument: If fd is not valid or does not have required mode.
    """
    try:
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    except (OSError, ValueError) as e:
        raise InvalidArgument(f"Invalid file descriptor: {fd!r}") from e

    accmode = flags & os.O_ACCMODE

    if mode == "r" and accmode not in (os.O_RDONLY, os.O_RDWR):
        raise InvalidArgument(f"File descriptor {fd!r} is not readable")
    elif mode == "w" and accmode not in (os.O_WRONLY, os.O_RDWR):
        raise InvalidArgument(f"File descriptor {fd!r} is not writable")
    elif mode == "rw" and accmode != os.O_RDWR:
        raise InvalidArgument(f"File descriptor {fd!r} is not readable and writable")
    else:
        raise ValueError(f"Invalid mode: {mode!r}")
