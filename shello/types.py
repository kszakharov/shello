from typing import Protocol, TypeAlias


class HasFileno(Protocol):
    def fileno(self) -> int: ...


FileDescriptorLike: TypeAlias = int | HasFileno
