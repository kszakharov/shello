---
# Code Quality and Correctness Fixes

## Overview
Fix three identified code quality and correctness issues: a critical logic bug in check_fd() that breaks file descriptor validation, a duplicate unused Protocol class in types.py, and a minor docstring formatting error in exceptions.py.

## Context
- Files involved: `shello/helpers.py`, `shello/types.py`, `shello/exceptions.py`, `tests/test_process.py`
- Related patterns: existing exception types (InvalidArgument, ShellError), Protocol-based type definitions
- Dependencies: none

## Development Approach
- **Testing approach**: Regular (code first, then tests)
- Complete each task fully before moving to the next
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Fix check_fd() logic bug in helpers.py

The else clause in check_fd() unconditionally raises ValueError even when a valid fd/mode combination is passed, because the if/elif conditions only raise on invalid combos and the else clause is reached on valid combos.

**Files:**
- Modify: `shello/helpers.py`

- [x] Read helpers.py lines 24-31 to confirm the exact bug
- [x] Move mode validation (ValueError for unrecognized mode) to before the fd flag checks, not as an else fallback
- [x] Ensure the function returns normally when fd and mode are both valid
- [x] Write a test in tests/test_process.py (or a helpers test file) that passes a valid writable fd with mode "w" and confirms no exception is raised
- [x] Write a test that passes an invalid mode string and confirms ValueError is raised
- [x] Run project test suite - must pass before task 2

### Task 2: Remove duplicate SupportsFileno from types.py

SupportsFileno is never imported or used anywhere. HasFileno is the one actually referenced by FileDescriptorLike.

**Files:**
- Modify: `shello/types.py`

- [x] Read types.py to confirm SupportsFileno is defined and unused
- [x] Grep codebase for any import of SupportsFileno to confirm it is truly unused
- [x] Delete the SupportsFileno class definition
- [x] Run project test suite - must pass before task 3

### Task 3: Fix double-period docstring in exceptions.py

Minor formatting issue: each arg description ends with `..` instead of `.`

**Files:**
- Modify: `shello/exceptions.py`

- [ ] Read exceptions.py lines 34-38
- [ ] Change all double periods to single periods in the ProcessError.__init__ docstring
- [ ] Run project test suite - must pass before task 4

### Task 4: Verify acceptance criteria

- [ ] manual test: instantiate a subprocess with a valid stdout fd and confirm it runs without raising ValueError
- [ ] run full test suite (pytest or equivalent from pyproject.toml)
- [ ] run linter (pyright if configured in pyproject.toml)
- [ ] verify test coverage meets 80%+

### Task 5: Update documentation

- [ ] update CLAUDE.md if internal patterns changed
- [ ] move this plan to `docs/plans/completed/`
