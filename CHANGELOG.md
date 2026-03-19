# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Support for Python 3.15
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

- `eintr_retry` decorator from `shello/decorators.py` (unused internal helper)

## [0.2.0] - 2026-03-08

### Added

- Support for Python 3.10 and 3.11

### Changed

- CI: Update `actions/checkout` to v6
- Rename properties `stdout_data` and `stderr_data` to `stdout` and `stderr`

## [0.1.0] - 2026-03-08

### Added

- Shell-like syntax for process execution (`shell.echo("hello")`)
- Unix-style pipeline support with `|` operator
- Complete I/O redirection (stdin/stdout/stderr)
- Process lifecycle management and state tracking
- Comprehensive error handling with detailed exceptions
- Timeout support and signal handling
- Text and binary mode shell variants
- Full type hints for Python 3.12+
- Comprehensive test suite with CI/CD
