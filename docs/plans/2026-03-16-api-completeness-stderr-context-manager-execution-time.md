---
# API Completeness: STDERR constant, Process context manager, Pipeline.execution_time

## Overview
Three missing API features documented or implied by the codebase but not yet implemented:
  1. `STDERR` sentinel constant (documented in README but not defined)
  2. `__enter__`/`__exit__` on `Process` for context manager support
  3. `execution_time` property on `Pipeline`

## Context
- Files involved: `shello/process.py`, `shello/pipeline.py`, `shello/__init__.py`, `tests/test_process.py`, `tests/test_pipeline.py`
- Related patterns: `DEVNULL = subprocess.DEVNULL`, `STDOUT = subprocess.STDOUT` in `process.py`; `Process.execution_time` uses `start_time`/`end_time` floats already set by `execute()`
- Dependencies: none

## Development Approach
- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Add STDERR constant

**Files:**
- Modify: `shello/process.py`
- Modify: `shello/__init__.py`

- [x] Define a `_STDERR_TYPE` sentinel class and `STDERR = _STDERR_TYPE()` after the existing `STDOUT` constant in `process.py`
- [x] Add `elif self._stdout_destination is STDERR: return 2` branch in `_get_stdout_handle()` (before the `isinstance(int)` check)
- [x] Add `elif self._stdout_destination is STDERR: redirects.append("1>&2")` in `__str__` stdout section
- [x] Import and re-export `STDERR` from `shello/__init__.py`; add to `__all__`
- [x] Write tests: pass `stdout=STDERR` to a Process and verify the output appears on stderr fd; verify `str()` includes `1>&2`
- [x] run project test suite - must pass before task 2

### Task 2: Context manager support for Process

**Files:**
- Modify: `shello/process.py`

- [x] Add `__enter__(self) -> Self` returning `self` (no execution — caller decides when to call `execute()`)
- [x] Add `__exit__(self, exc_type, exc_val, exc_tb) -> None` that calls `self.kill()` when `self.state` is `RUNNING` or `SPAWNING`, and returns `None` (does not suppress exceptions)
- [x] Write tests: verify `with Process(...) as p:` works and `p` is the process instance; verify a running background process is killed on context exit; verify `execute()` result is accessible inside the `with` block
- [x] run project test suite - must pass before task 3

### Task 3: Pipeline.execution_time property

**Files:**
- Modify: `shello/pipeline.py`

- [ ] Add `execution_time` property that returns `max(end_times) - min(start_times)` across all processes, or `None` if any start/end time is missing
- [ ] Write tests: verify `execution_time` is a positive float after pipeline executes; verify it returns `None` before execution
- [ ] run project test suite - must pass before task 4

### Task 4: Verify acceptance criteria

- [ ] manual test: `from shello import STDERR; Process("echo", "hi", stdout=STDERR).execute()` — output should appear on stderr
- [ ] manual test: context manager `with Process("sleep", "10", wait=False) as p: p.execute()` — process killed on exit
- [ ] manual test: `(Process("echo", "hi") | Process("wc", "-c")).execute().execution_time` returns a float
- [ ] run full test suite: `uv run pytest`
- [ ] run linter: `uv run pyright`
- [ ] verify test coverage meets 80%+

### Task 5: Update documentation

- [ ] no README changes needed (STDERR already documented; add context manager and Pipeline.execution_time examples if helpful)
- [ ] move this plan to `docs/plans/completed/`
