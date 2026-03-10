# Changelog

All notable changes to this project will be documented in this file.

## [Unreliased]

### Added

- Support for Python 3.15

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
