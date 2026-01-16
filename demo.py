#!/usr/bin/env python3
"""
Demo script showing shello library capabilities.
"""

from shello import STDOUT, Process, ProcessError, TimeoutError, shell


def run_example(process: Process) -> None:
    """Run a shello Process and print its details and results."""

    if process.env:
        env = "\n\t".join(f"{k}={v}" for k, v in process.env.items())
        print(f"   Environment:\n\t{env}")
    print(f"   Command: {process}")

    try:
        process.execute()
    except ProcessError, TimeoutError:
        pass

    std_output = process.stdout_data.strip()
    if "\n" in std_output:
        std_output = "\n\t".join(std_output.splitlines())
        print(f"   Output:\n\t{std_output}")
    else:
        print(f"   Output: {std_output}")

    if process.stderr_data:
        stderr_data = process.stderr_data.strip()
        if "\n" in stderr_data:
            stderr_data = "\n\t".join(stderr_data.splitlines())
            print(f"   Error Output:\n\t{stderr_data}")
        else:
            print(f"   Error Output: {stderr_data}")
    print(f"   Exit code: {process.returncode}")


def main():
    print("=== Shello Library Demo ===\n")

    # Basic command execution
    print("1. Basic command execution:")
    run_example(shell.echo("Hello, World!"))
    print()

    # Command with arguments
    print("2. Command with arguments:")
    run_example(shell.wc("-c", stdin="Hello World"))
    print()

    # Pipeline support
    print("3. Pipeline support:")
    run_example(shell.echo("one two three") | shell.wc("-w"))
    print()

    # Error handling
    print("4. Error handling:")
    run_example(shell.false())
    print()

    # Environment variables
    print("5. Environment variables:")
    run_example(shell.sh("-c", "echo $CUSTOM_VAR", env={"CUSTOM_VAR": "custom_value"}))
    print()

    # Std error capture
    print("6. Std error capture:")
    run_example(shell.ls("missing_file"))
    print()

    # I/O redirection
    print("7. I/O redirection:")
    run_example(shell.ls("missing_file", stderr=STDOUT))
    print()

    # I/O redirection, no reader
    print("8. Long command:")
    run_example(shell.yes() | shell.echo("Message"))
    print()

    # Timeout
    print("9. Timeout:")
    run_example(shell.sleep("5", timeout=0.1))
    print()

    # Timeout, capture output
    print("10. Timeout, capture output:")
    run_example(shell.ping("google.com", timeout=0.2))
    print()

    print("=== Demo Complete ===")


if __name__ == "__main__":
    main()
