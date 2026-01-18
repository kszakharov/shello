import functools
import threading
import weakref
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from .exceptions import AlreadyRunError

R = TypeVar("R")
SelfT = TypeVar("SelfT")


def with_callback(
    on_done: Callable[[SelfT], None],
    on_error: Callable[[SelfT, Exception], R] | None = None,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """
    A decorator that calls `on_done` after the function finishes,
    and `on_error` if an exception occurs.
    """

    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapper(self: SelfT, *args: Any, **kwargs: Any) -> R:
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                if on_error is not None:
                    return on_error(self, e)
                raise
            finally:
                on_done(self)

        return wrapper

    return decorator


def run_once(func):
    """
    Decorator that ensures a method can only be executed once per instance.

    Uses a WeakKeyDictionary to track execution state per instance, avoiding
    memory leaks. Thread-safe with double-checked locking pattern.

    Args:
        func: The function to decorate

    Returns:
        Decorated function that raises AlreadyRunError on subsequent calls

    Raises:
        AlreadyRunError: If the method has already been called for this instance
    """
    run_state = weakref.WeakKeyDictionary()  # {instance: (has_run, lock)}
    state_lock = threading.Lock()

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Initialize per-instance state if needed
        with state_lock:
            if self not in run_state:
                run_state[self] = [threading.Lock(), threading.Event()]
            lock, done = run_state[self]

        if done.is_set():
            raise AlreadyRunError(f"{func.__name__} has already been run once for this instance.")

        with lock:
            if done.is_set():
                raise AlreadyRunError(f"{func.__name__} has already been run once for this instance.")

            done.set()
            return func(self, *args, **kwargs)

    return wrapper
