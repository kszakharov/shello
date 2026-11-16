# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Support for Python 3.15
- Project logo and status badges to the README

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

[Unreleased]: https://github.com/kszakharov/shello/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/kszakharov/shello/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/kszakharov/shello/releases/tag/v0.1.0
