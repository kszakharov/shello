# Shello

A modern Python library for shell-style process execution with elegant syntax and powerful features.

## Features

- **Shell-like syntax**: `shell.echo("hello")` instead of complex subprocess calls
- **Pipeline support**: `shell.echo("hello") | shell.wc("-w")` for Unix-style pipes
- **I/O redirection**: Support for stdin/stdout/stderr redirection with `DEVNULL`, `STDOUT`, `STDERR`
- **Modern Python**: Built with Python 3.11+ features and type hints
- **Comprehensive error handling**: Clear exceptions with detailed error information
- **Flexible configuration**: Environment variables, working directory, and more

## Quick Start

```python
from shello import shell

# Basic command execution
result = shell.echo("Hello, World!").execute()
print(result.stdout_data())  # "Hello, World!\n"

# Command with arguments
result = shell.ls("-la", "/tmp").execute()

# Pipelines
result = (shell.echo("one two three") | shell.wc("-w")).execute()
print(result.stdout_data())  # "3\n"

# With stdin
result = shell.wc("-c", stdin="Hello World").execute()
print(result.stdout_data())  # "11\n"

# Environment variables
result = shell.env("CUSTOM_VAR=value").execute()

# I/O redirection
result = shell.echo("error", stderr=STDOUT).execute()  # stderr to stdout
result = shell.echo("data", stdout=DEVNULL).execute()  # discard output
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

### Process Class

Represents a process that can be executed.

#### Constructor

```python
Process(program, *args,
       stdin=DEVNULL, stdout=None, stderr=None,
       cwd=None, env=None, check=True, text=True, **kwargs)
```

**Parameters:**
- `program`: Command to execute
- `*args`: Command line arguments
- `stdin`: Input source (`DEVNULL`, string, bytes, file-like object)
- `stdout`: Output destination (`None`, `DEVNULL`, `STDOUT`, `STDERR`, file path, file object)
- `stderr`: Error output destination (same options as stdout)
- `cwd`: Working directory
- `env`: Environment variables dict
- `check`: Raise exception on non-zero exit (default: `True`)
- `text`: Text mode for I/O (default: `True`)
- `**kwargs`: Additional subprocess arguments

#### Methods

- `execute() -> Process`: Execute the process and wait for completion
- `wait() -> int`: Wait for process completion and return exit code
- `kill(signal=15) -> None`: Send signal to process
- `pid() -> int | None`: Get process ID
- `stdout_data() -> str`: Get captured stdout
- `stderr_data() -> str`: Get captured stderr
- `returncode() -> int`: Get process return code

#### Pipeline Operator

```python
# Unix-style pipelines
result = (shell.echo("hello") | shell.wc("-c")).execute()

# Multi-step pipelines
result = (shell.cat("file.txt") | shell.grep("pattern") | shell.wc("-l")).execute()
```

### Constants

- `DEVNULL`: `/dev/null` redirection
- `STDOUT`: stdout redirection marker
- `STDERR`: stderr redirection marker

### Exception Hierarchy

```python
ShellError          # Base exception
├── ProcessError    # Process execution failures
├── InvalidArgument # Invalid arguments
└── InvalidOperation # Invalid operations
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
