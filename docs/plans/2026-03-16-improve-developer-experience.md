---
# Improve Developer Experience: Error Messages, Logging, and Test Coverage

## Overview
Three targeted improvements to shello's developer experience: fix missing exception exports so users can catch all raised exceptions, improve logging in silent failure paths, and add tests for uncovered code paths (UnexpectedExitCodeError, check_returncode(), pre-execution property access, wait=False).

## Context
- Files involved: `shello/__init__.py`, `shello/process.py`, `tests/test_process.py`
- Related patterns: existing pytest style in `tests/test_process.py`, existing logger usage in `shello/process.py`
- Dependencies: none

## Development Approach
- **Testing approach**: Regular (fix production code first, add/update tests after)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Fix missing exception exports

**Files:**
- Modify: `shello/__init__.py`

The following exceptions are raised in public code paths but not exported in `__all__`, making it impossible for users to catch them without importing internals:
- `InvalidOperation` (8+ raise sites in process.py)
- `UnexpectedExitCodeError` (raised when check=True and exit code is unexpected)

- [x] Import `InvalidOperation` and `UnexpectedExitCodeError` from `.exceptions` in `__init__.py`
- [x] Add both to `__all__`
- [x] Verify `from shello import InvalidOperation, UnexpectedExitCodeError` works
- [x] Run test suite - must pass before task 2

### Task 2: Improve logging in silent failure paths

**Files:**
- Modify: `shello/process.py`

Two logging gaps make failures hard to diagnose:
- `_cleanup_resources()` (line 472) silently swallows file handle close errors with `pass` and no log
- `_write_stdin()` (line 281-283) catches generic `Exception` and stores it as a plain `Exception` instead of a domain type, losing context

- [x] In `_cleanup_resources()`, replace bare `pass` with `logger.warning("%s: failed to close file handle: %s", self.program, e)` (keep `except Exception as e:`)
- [x] In `_write_stdin()` generic exception handler, wrap the stored exception as `ProcessError` instead of bare `Exception` so it carries proper type information
- [x] Run test suite - must pass before task 3

### Task 3: Add missing test coverage for error paths

**Files:**
- Modify: `tests/test_process.py`

Several public API paths and exception types have zero test coverage:

- [x] Add test: `UnexpectedExitCodeError` raised when `check=True` and process exits non-zero (import from `shello` directly to verify export works)
- [x] Add test: `check_returncode()` called directly on completed process raises `UnexpectedExitCodeError` for non-zero exit
- [x] Add test: accessing `.stderr` before `execute()` raises `InvalidOperation`
- [x] Add test: accessing `.returncode` before `execute()` raises `InvalidOperation`
- [x] Add test: `wait=False` — process created but not waited, then `.wait()` called explicitly completes successfully
- [x] Run full test suite - must pass

### Task 4: Verify acceptance criteria

- [x] manual test: `python -c "from shello import InvalidOperation, UnexpectedExitCodeError; print('exports ok')"`
- [x] run full test suite: `uv run pytest`
- [x] run linter: `uv run pyright`
- [x] verify test coverage meets 80%+: `uv run pytest --cov`

### Task 5: Update documentation

- [ ] update CLAUDE.md if internal patterns changed
- [ ] move this plan to `docs/plans/completed/`
