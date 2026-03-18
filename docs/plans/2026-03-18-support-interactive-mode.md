# Support Interactive Mode for Process Execution

## Overview
Add an `interactive` parameter to `Process` that connects stdin/stdout/stderr directly to the parent terminal, allowing the user to interact with the running process in real time (e.g., a Python REPL, an editor, a prompt).

## Context
- Files involved:
  - `shello/process.py` — core changes: new parameter, handle methods, background monitor
  - `tests/test_process.py` — new tests
  - `README.md` — usage example
- Related patterns: existing `wait`, `capture_stdout`, `print_stdout` parameters follow similar opt-in override conventions
- Dependencies: none (uses stdlib `subprocess` with `None` fd inheritance)

## Development Approach
- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Add `interactive` parameter to `Process`

**Files:**
- Modify: `shello/process.py`

- [x] Add `interactive: bool = False` to both `@overload` signatures and the actual `__init__`
- [x] Store `self.interactive = interactive` in `__init__`
- [x] In `_get_stdin_handle()`: when `self.interactive`, return `None` so `subprocess.Popen` inherits the parent's stdin fd directly — this gives the child process a real TTY, enabling raw input, cursor keys, etc. A PIPE would require manual forwarding and would break TTY-dependent programs
- [x] In `_get_stdout_handle()`: when `self.interactive`, return `None` for the same reason (child writes directly to the parent terminal, preserving color codes and cursor control)
- [x] In `_get_stderr_handle()`: when `self.interactive`, return `None`
- [x] In `_background_monitor()`: when `self.interactive`, skip stdin/stdout/stderr threads and only start `_handle_execution`
- [x] Add validation in `__init__`: raise `InvalidArgument` if `interactive=True` and `stdin` is `str` or `bytes` (incompatible — no pipe to write to)
- [x] Run tests: `uv run pytest` — must pass

### Task 2: Write tests for interactive mode

**Files:**
- Modify: `tests/test_process.py`

- [x] Test: `interactive=True` executes a simple command (`true`) and completes successfully
- [x] Test: `interactive=True` with `wait=False` starts and can be waited on
- [x] Test: `interactive=True` and `stdin=b"data"` raises `InvalidArgument`
- [x] Test: `interactive=True` leaves `stdout` and `stderr` as empty bytes/str after execution
- [x] Test: `interactive=True` process with a short-lived command returns correct `returncode`
- [x] Run tests: `uv run pytest` — must pass

### Task 3: Verify acceptance criteria

- [ ] `uv run pytest`
- [ ] `uv run pyright`

### Task 4: Update documentation

- [ ] Add `interactive` parameter to the `Process` constructor docs in `README.md`
- [ ] Add an "Interactive Mode" example section to `README.md`
- [ ] Move this plan to `docs/plans/completed/`
