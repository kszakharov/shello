---
# Fix Interactive Mode: PTY Support via InteractiveProcess

## Overview

The `interactive=True` mode currently passes `stdin=stdout=stderr=None` to `subprocess.Popen`, which inherits the parent's file descriptors. This works for simple programs but breaks for terminal programs like SSH. SSH requires a real PTY: without one it skips raw mode, no remote PTY is allocated, and escape sequences print as garbled text (the `s7ul...` output seen).

Fix: extract all interactive-mode logic into a new `InteractiveProcess` class in `shello/interactive.py` that inherits from `Process`. It overrides `execute()` to use `pty.fork()` instead of subprocess, runs a `_pty_proxy` background thread to relay I/O, and overrides `kill()`/`pid`/`returncode`. `Shell.__call__` and `__getattr__` return `InteractiveProcess` when `interactive=True` is passed. `process.py` has its `if self.interactive:` branches removed.

## Context

- Files involved: `shello/process.py`, `shello/shell.py`, `shello/interactive.py` (new), `shello/__init__.py`, `shello/pipeline.py`, `tests/test_process.py`
- Related patterns: `@with_callback(on_done=..._task_done())` for thread lifecycle, `_background_monitor`, state machine PENDING→SPAWNING→RUNNING→TERMINATED
- Dependencies: stdlib `pty`, `select`, `tty`, `termios`, `os` (all Python 3.10+ built-ins)

## Development Approach

- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- All pyright type checks must pass
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Create shello/interactive.py with InteractiveProcess

**Files:**
- Create: `shello/interactive.py`
- Modify: `shello/process.py`

- [x] Create `shello/interactive.py` importing `pty`, `select`, `tty`, `termios`, `os`, `time`, `threading`, `cast`, and `Process`/`ProcessState`/`ProcessError`/`InvalidOperation` from the sibling modules
- [x] Define `InteractiveProcess(Process)` — constructor calls `super().__init__()` and additionally initializes `_pty_pid: int | None = None` and `_pty_returncode: int | None = None`
- [x] Override `execute()`: set state to SPAWNING, call `pty.fork()` in the main thread; in the child, call `os.execvpe` (respecting `cwd` via `os.chdir`) and `os._exit(127)` on failure; in the parent, record `_pty_pid`, set `start_time`, transition to RUNNING, start `_pty_proxy` thread via `_background_monitor_pty()`, call `wait()` if `self._wait`, return `self`. Wrap fork in `try/except OSError` that resets state to PENDING and raises `ProcessError`
- [x] Add `_background_monitor_pty(self, master_fd: int) -> None` decorated with `@with_callback(on_done=lambda self: cast("InteractiveProcess", self)._task_done())`; body: save terminal settings with `termios.tcgetattr(sys.stdin)`, call `tty.setraw(sys.stdin)`, run `select.select` loop forwarding stdin→master and master→stdout until `OSError` or empty read from master, restore settings in `finally`, close `master_fd`, call `os.waitpid(self._pty_pid, 0)`, convert result with `os.waitstatus_to_exitcode()` into `self._pty_returncode`, set `self.end_time`
- [x] Override `returncode` property to return `self._pty_returncode` (raise `InvalidOperation` if still None / not terminated)
- [x] Override `pid` property to return `self._pty_pid`
- [x] Override `kill(signal=15)` to call `os.kill(self._pty_pid, signal)` when `_pty_pid` is set
- [x] In `process.py`: remove the `if self.interactive: return None` early-returns in `_get_stdin_handle`, `_get_stdout_handle`, `_get_stderr_handle`, and remove the `if not self.interactive:` guard in `_background_monitor` (these code paths are now only reached for non-interactive processes)
- [x] Run `uv run pytest` — must pass before Task 2

### Task 2: Wire InteractiveProcess into Shell and exports

**Files:**
- Modify: `shello/shell.py`
- Modify: `shello/__init__.py`
- Modify: `shello/pipeline.py`

- [ ] In `shell.py`: import `InteractiveProcess` from `.interactive`; in both `__call__` and the `create_process` closure inside `__getattr__`, check `options.get("interactive")` and return `InteractiveProcess(program, *args, **options)` instead of `Process(...)` when true
- [ ] In `__init__.py`: add `InteractiveProcess` to imports from `.interactive` and to `__all__`
- [ ] In `pipeline.py`: replace `process.interactive` attribute check with `isinstance(process, InteractiveProcess)` (import `InteractiveProcess` there); or verify the check is no longer needed after the refactor
- [ ] Run `uv run pytest` — must pass before Task 3

### Task 3: Update and extend tests

**Files:**
- Modify: `tests/test_process.py`

- [ ] Verify all existing `TestInteractiveMode` tests still pass (they use `true`, `false`, `sh -c "sleep 0.05"`)
- [ ] Add `test_interactive_pty_env` — run `InteractiveProcess` with `env={...}` on a command that prints an env var; verify returncode 0
- [ ] Add `test_interactive_pty_cwd` — run `InteractiveProcess` with `cwd="/tmp"` running `pwd`; verify returncode 0
- [ ] Add `test_interactive_kill` — start `InteractiveProcess("sleep", "10", wait=False)`, call `execute()`, then `kill()`, then `wait(check=False)`; verify returncode indicates signal termination
- [ ] Run `uv run pytest` — must pass
- [ ] Run `uv run pyright` — must pass clean

### Task 4: Verify acceptance criteria

- [ ] Run `uv run pytest` (full test suite)
- [ ] Run `uv run pyright`
- [ ] Verify test coverage ≥ 80%

### Task 5: Update documentation

- [ ] Update README.md if interactive mode behavior docs need adjusting
- [ ] Move this plan to `docs/plans/completed/`
