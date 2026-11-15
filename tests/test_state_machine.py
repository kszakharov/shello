"""Test state machine for thread safety and resource leaks."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from shello import Command
from shello.exceptions import InvalidOperation, ProcessError
from shello.process import ProcessState


class TestStateMachineLeaks:
    """Test state machine for resource leaks and thread safety."""

    def test_single_state_transition_sequence(self):
        """Test normal state transition sequence."""
        command = Command("echo", "test")

        # After execution, should go to TERMINATED
        process = command.execute()
        assert process.state == ProcessState.TERMINATED

    def test_failed_state_transition(self):
        """Test TERMINATED state for non-zero exit codes."""
        command = Command("false", check=False)  # Command that exits with 1
        process = command.execute()
        assert process.state == ProcessState.TERMINATED

    def test_state_transition_prevents_reuse(self):
        """Test that terminated processes cannot be reused."""
        command = Command("echo", "test")
        process = command.execute()

        assert process.state == ProcessState.TERMINATED

        # Should not be able to execute again
        with pytest.raises(InvalidOperation, match="already executed"):
            process.execute()

    def test_kill_state_transition(self):
        """Test TERMINATED state transition."""
        command = Command("sleep", "10", wait=False)
        process = command.execute()

        # Give time for command to start
        time.sleep(0.1)

        # Kill the process
        process.kill()

        # Give time for command to kill and finish
        time.sleep(0.1)

        # Should be in TERMINATED state
        assert process.state == ProcessState.TERMINATED

    def test_state_property_thread_safety(self):
        """Test that state property is thread-safe."""
        command = Command("sleep", "0.1", wait=False)
        process = command.execute()

        states = []

        def collect_states():
            for _ in range(100):
                states.append(process.state)

        threads = [threading.Thread(target=collect_states) for _ in range(5)]

        for thread in threads:
            thread.start()

        # Let the process finish while the reader threads are polling its state
        process.wait()

        for thread in threads:
            thread.join()

        # All states should be valid ProcessState enums
        assert all(isinstance(state, ProcessState) for state in states)

    def test_concurrent_execution_protection(self):
        """Test that concurrent execution attempts are properly protected."""
        command = Command("echo", "test")

        results = []
        errors = []

        process = command.execute()
        results.append(process)

        def try_execute():
            try:
                process.execute()
                results.append(process)
            except Exception as e:
                errors.append(e)

        # Try to execute from multiple threads
        threads = [threading.Thread(target=try_execute) for _ in range(9)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Only one execution should succeed
        assert len(results) == 1
        assert len(errors) == 9
        assert all(isinstance(e, InvalidOperation) for e in errors)

    def test_large_concurrent_workload(self):
        """Test state machine under high concurrent load."""
        processes = [Command("echo", f"test{i}") for i in range(20)]

        def execute_process(command):
            try:
                return command.execute().state
            except Exception as e:
                return e

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(execute_process, p) for p in processes]
            results = [future.result() for future in as_completed(futures)]

        # All should be TERMINATED or FAILED states
        successful_results = [r for r in results if isinstance(r, ProcessState)]
        assert len(successful_results) == 20

        assert all(r == ProcessState.TERMINATED for r in successful_results)

    def test_lock_timeout_protection(self):
        """Test that a held lock delays completion but doesn't cause a deadlock."""
        process = Command("sleep", "0.1").execute()  # starts immediately

        lock_held = threading.Event()

        def slow_operation():
            with process._lock:
                lock_held.set()
                time.sleep(0.2)

        slow_thread = threading.Thread(target=slow_operation)
        slow_thread.start()
        assert lock_held.wait(timeout=1.0)  # lock is definitely held now

        # The process exits after ~0.1s, but the TERMINATED state change
        # needs the lock, so wait() should return once it is released (~0.2s).
        start_time = time.time()
        process.wait()
        elapsed = time.time() - start_time

        assert process.state is ProcessState.TERMINATED
        assert elapsed < 1.0  # no deadlock

        slow_thread.join()

    def test_exception_state_consistency(self):
        """Test that state remains consistent after exceptions."""
        # Test with command that doesn't exist
        command = Command("nonexistent_command_12345", wait=False)
        with pytest.raises(ProcessError, match="Command not found: nonexistent_command_12345"):
            command.execute()

    def test_state_access_after_cleanup(self):
        """Test state access behavior after command completion."""
        command = Command("echo", "test")
        process = command.execute()

        # State should still be accessible after completion
        assert process.state == ProcessState.TERMINATED

        # Multiple accesses should work
        for _ in range(10):
            assert process.state == ProcessState.TERMINATED


class TestLockBehavior:
    """Specific tests for lock behavior and deadlock prevention."""

    pass
