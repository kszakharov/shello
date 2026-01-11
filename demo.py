#!/usr/bin/env python3
"""
Demo script showing shello library capabilities.
"""

from shello import STDOUT, ProcessError, shell


def main():
    print("=== Shello Library Demo ===\n")

    # Basic command execution
    print("1. Basic command execution:")
    result = shell.echo("Hello, World!").execute()
    print(f"   Output: {result.stdout_data().strip()}")
    print(f"   Exit code: {result.returncode()}")
    print()

    # Command with arguments
    print("2. Command with arguments:")
    result = shell.wc("-c", stdin="Hello World").execute()
    print(f"   Character count: {result.stdout_data().strip()}")
    print()

    # Pipeline support
    print("3. Pipeline support:")
    result = (
        shell.echo("one two three") | shell.wc("-w")
    ).execute()
    print(f"   Word count: {result.stdout_data().strip()}")
    print()

    # Error handling
    print("4. Error handling:")
    try:
        shell.false().execute()
    except ProcessError as e:
        print(f"   Caught error: {e.exit_code}")
    print()

    # Environment variables
    print("5. Environment variables:")
    result = shell.sh(
        "-c", "echo $CUSTOM_VAR", env={"CUSTOM_VAR": "custom_value"}
    ).execute()
    print(f"   Custom env var: {result.stdout_data().strip()}")
    print()

    # I/O redirection
    print("6. I/O redirection:")
    result = shell.echo("error message", stderr=STDOUT).execute()
    print(f"   Stderr to stdout: {result.stdout_data().strip()}")
    print()

    print("=== Demo Complete ===")


if __name__ == "__main__":
    main()
