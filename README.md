# Shello [![Tests](https://github.com/kszakharov/shello/actions/workflows/ci.yml/badge.svg)](https://github.com/kszakharov/shello/actions/workflows/ci.yml) [![Version](https://img.shields.io/pypi/v/shello)](https://pypi.org/project/shello) [![Python Version](https://img.shields.io/pypi/pyversions/shello.svg)](https://pypi.org/project/shello)

A modern Python library for shell-style process execution with elegant syntax and powerful features.

## Features

- **Shell-like syntax**: `shell.echo("hello")` instead of complex subprocess calls
- **Pipeline support**: `shell.echo("hello") | shell.wc("-w")` for Unix-style pipes
- **I/O redirection**: Support for stdin/stdout/stderr redirection with `DEVNULL`, `STDOUT`, `STDERR`
- **Modern Python**: Built with Python 3.10+ features and type hints
- **Comprehensive error handling**: Clear exceptions with detailed error information
- **Flexible configuration**: Environment variables, working directory, and more

## Quick Start

```python
from shello import shell

# Basic command execution
result = shell.echo("Hello, World!").execute()
print(result.stdout)  # "Hello, World!\n"

# Command with arguments
result = shell.ls("-la", "/tmp").execute()

# Pipelines
result = (shell.echo("one two three") | shell.wc("-w")).execute()
print(result.stdout)  # "3\n"

# With stdin
result = shell.wc("-c", stdin="Hello World").execute()
print(result.stdout)  # "11\n"

# Environment variables
result = shell.env("CUSTOM_VAR=value").execute()

# I/O redirection
result = shell.echo("error", stderr=STDOUT).execute()  # stderr to stdout
result = shell.echo("data", stdout=DEVNULL).execute()  # discard output

# Acceptable exit codes
result = shell.command_that_might_fail(ok_exitcodes=(0, 1)).execute()  # accept 0 or 1
result = shell.any_command(ok_exitcodes=ANY_EXITCODE).execute()        # accept any exit code
```

## Installation

```bash
pip install shello
# or with uv
uv add shello
```

## API Reference

### Shell Class

The main factory class for creating Process objects.

```python
from shello import Shell

# Create shell with default options
shell = Shell(check=False, cwd="/tmp")

# Create processes
process1 = shell("echo", "hello")
process2 = shell.echo("hello")  # Attribute access (underscores -> hyphens)
```

### Convenience Objects

Two module-level `Shell` instances are provided for quick use:

```python
from shello import shell, binary_shell

# shell: text=True — .stdout/.stderr return str
result = shell.echo("hello").execute()
print(result.stdout)  # "hello\n"

# binary_shell: text=False — .stdout/.stderr return bytes
result = binary_shell.echo("hello").execute()
print(result.stdout)  # b"hello\n"
```

### Process Class

Represents a process that can be executed.

#### Constructor

```python
Process(program, *args,
       stdin=None, stdout=None, stderr=None,
       cwd=None, env=None, check=True, ok_exitcodes=0, text=False,
       timeout=None, capture_stdout=True, capture_stderr=True,
       print_stdout=False, print_stderr=False, wait=True, **kwargs)
```

`Process` is generic over `AnyStr`: use `text=True` to get a `Process[str]` where `.stdout`/`.stderr` return `str`, or `text=False` (default) to get a `Process[bytes]` where they return `bytes`. The module-level `shell` convenience object defaults to `text=True`.

**Parameters:**
- `program`: Command to execute
- `*args`: Command line arguments
- `stdin`: Input source (string, bytes, file-like object, or `Path`)
- `stdout`: Output destination (`None`, `DEVNULL`, `STDOUT`, file path, file object)
- `stderr`: Error output destination (same options as stdout)
- `cwd`: Working directory
- `env`: Environment variables dict
- `check`: Raise exception on unacceptable exit (default: `True`)
- `ok_exitcodes`: Acceptable exit codes (default: `0`, use `ANY_EXITCODE` for any) - can be int or container
- `text`: Text mode for I/O; `True` → `Process[str]`, `False` (default) → `Process[bytes]`
- `timeout`: Maximum execution time in seconds; raises `TimeoutError` if exceeded (default: `None`)
- `capture_stdout`: Capture stdout for retrieval via `.stdout` (default: `True`)
- `capture_stderr`: Capture stderr for retrieval via `.stderr` (default: `True`)
- `print_stdout`: Print stdout to console during execution (default: `False`)
- `print_stderr`: Print stderr to console during execution (default: `False`)
- `wait`: Block until process completes after `execute()` (default: `True`); set to `False` to start without blocking, then call `.wait()` explicitly
- `**kwargs`: Additional subprocess arguments

#### Methods

- `execute() -> Self`: Execute the process and return self (raises on error if `check=True`)
- `wait() -> Self`: Wait for process completion and return self
- `check_returncode() -> None`: Raise `UnexpectedExitCodeError` if exit code is not in `ok_exitcodes`
- `kill(signal=15) -> None`: Send signal to process
- `pid -> int | None`: Get process ID
- `stdout -> str | bytes`: Get captured stdout (`str` when `text=True`, `bytes` when `text=False`)
- `stderr -> str | bytes`: Get captured stderr (`str` when `text=True`, `bytes` when `text=False`)
- `returncode -> int`: Get process return code
- `execution_time -> float | None`: Wall-clock execution time in seconds, or `None` if not yet complete

#### Pipeline Operator

```python
# Unix-style pipelines
result = (shell.echo("hello") | shell.wc("-c")).execute()

# Multi-step pipelines
result = (shell.cat("file.txt") | shell.grep("pattern") | shell.wc("-l")).execute()
```

### Constants

- `ANY_EXITCODE`: Accepts any valid exit code (0-255)
- `DEVNULL`: `/dev/null` redirection
- `STDOUT`: stdout redirection marker
- `STDERR`: stderr redirection marker

### Exception Hierarchy

```python
ShellError                    # Base exception
├── ProcessError              # Process execution failures (command not found, subprocess error)
├── InvalidArgument           # Invalid arguments passed to a process
├── InvalidOperation          # Invalid operations (e.g. calling execute() twice)
├── TimeoutError              # Process exceeded the configured timeout
└── UnexpectedExitCodeError   # Exit code not in ok_exitcodes (raised when check=True)
```

## Examples

### Environment Variables

```python
env = {"PATH": "/usr/bin:/bin", "DEBUG": "1"}
result = shell.python("script.py", env=env).execute()
```

### Working Directory

```python
result = shell.ls("-la", cwd="/home/user").execute()
```

### Error Handling

```python
try:
    shell.nonexistent_command().execute()
except ProcessError as e:
    print(f"Command failed: {e.exit_code}")
    print(f"Output: {e.stdout}")
```

### I/O Redirection

```python
# Capture stderr
result = shell.command("2>&1", stderr=STDOUT).execute()

# Discard output
result = shell.verbose_command(stdout=DEVNULL).execute()

# Output to file
result = shell.echo("data", stdout="output.txt").execute()
```

### Background Processing

```python
# Execute without waiting
process = shell.long_running_command(wait=False)

# Later...
process.wait()  # Wait for completion
```

### Context Manager

```python
# Process is automatically killed on context exit if still running
with Process("sleep", "10", wait=False) as p:
    p.execute()
    # ... do other work ...
# p.kill() called automatically on exit
```

### Pipeline Execution Time

```python
pipeline = (shell.echo("hello") | shell.wc("-c")).execute()
print(f"Pipeline took {pipeline.execution_time:.3f}s")
```

## Development

```bash
# Clone repository
git clone https://github.com/kszakharov/shello
cd shello

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run demo
uv run python demo.py
```

## License

MIT License - see LICENSE file for details.
