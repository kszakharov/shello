---
# Update CHANGELOG.md with Changes Since v0.2.0

## Overview
Update CHANGELOG.md to document all notable changes made since v0.2.0 that are not yet reflected in the [Unreleased] section. Also fix the typo "Unreliased" -> "Unreleased".

## Context
- Files involved: `CHANGELOG.md`
- Completed plans reviewed: `docs/plans/completed/2026-03-15-code-quality-correctness-fixes.md`, `2026-03-16-improve-developer-experience.md`, `2026-03-16-api-completeness-stderr-context-manager-execution-time.md`, `2026-03-18-support-interactive-mode.md`, `2026-03-18-fix-interactive-mode-pty.md`
- Git diff since v0.2.0 used to identify all changes

## Development Approach
- This is a documentation-only change; no code changes, no tests required
- Complete the single task fully before marking done

## Implementation Steps

### Task 1: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

- [x] Fix typo in heading: "Unreliased" -> "Unreleased"
- [x] Add the following under [Unreleased]:

  ### Added
  - Interactive mode via `InteractiveProcess` with PTY allocation (`interactive=True` on `Shell`)
  - Context manager support for `Process` (`with shell.cmd() as p:`)
  - `Pipeline.execution_time` property for timing pipeline runs
  - `STDERR` sentinel constant for redirecting stdout to stderr
  - Export `InvalidOperation` and `UnexpectedExitCodeError` from the public API (`shello`)

  ### Changed
  - CI: Moved `.deb` build to a separate reusable workflow (`.github/workflows/deb.yml`)
  - Improved logging in silent failure paths

  ### Fixed
  - `check_fd()` logic bug
  - Pyright type errors; added `AnyStr` generics to `Process`

  ### Removed
  - `shello/decorators.py` (unused internal module)

### Task 2: Verify and complete

- [x] Review CHANGELOG.md for formatting consistency with prior version entries
- [x] Move this plan to `docs/plans/completed/`
