"""Test state machine for thread safety and resource leaks."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from shello import Process
from shello.exceptions import InvalidOperation
from shello.process import ProcessState


class TestStateMachineLeaks:
    """Test state machine for resource leaks and thread safety."""

    def test_state_initialization(self):
        """Test process starts in PENDING state."""
        process = Process("echo", "test")
        assert process.state == ProcessState.PENDING
        assert process._process is None

    def test_single_state_transition_sequence(self):
        """Test normal state transition sequence."""
        process = Process("echo", "test")

        # Should be PENDING initially
        assert process.state == ProcessState.PENDING

        # After execution, should go to TERMINATED
        process.execute()
        assert process.state == ProcessState.TERMINATED

    def test_failed_state_transition(self):
        """Test TERMINATED state for non-zero exit codes."""
        process = Process("false", check=False)  # Command that exits with 1
        process.execute()
        assert process.state == ProcessState.TERMINATED

    def test_state_transition_prevents_reuse(self):
        """Test that terminated processes cannot be reused."""
        process = Process("echo", "test")
        process.execute()

        assert process.state == ProcessState.TERMINATED

        # Should not be able to execute again
        with pytest.raises(InvalidOperation, match="already executed"):
            process.execute()

    def test_kill_state_transition(self):
        """Test TERMINATED state transition."""
        process = Process("sleep", "10")

        # Start in background thread
        def execute_process():
            try:
                process.execute()
            except Exception:
                pass  # Ignore exceptions from kill

        thread = threading.Thread(target=execute_process)
        thread.start()

        # Give time for process to start
        time.sleep(0.1)

        # Kill the process
        process.kill()

        # Should be in TERMINATED state
        assert process.state == ProcessState.TERMINATED

        thread.join(timeout=1.0)

    def test_state_property_thread_safety(self):
        """Test that state property is thread-safe."""
        process = Process("echo", "test")
        states = []

        def collect_states():
            for _ in range(100):
                states.append(process.state)

        threads = [threading.Thread(target=collect_states) for _ in range(5)]

        for thread in threads:
            thread.start()

        # Execute process while threads are running
        process.execute()

        for thread in threads:
            thread.join()

        # All states should be valid ProcessState enums
        assert all(isinstance(state, ProcessState) for state in states)

    def test_concurrent_execution_protection(self):
        """Test that concurrent execution attempts are properly protected."""
        process = Process("echo", "test")
        results = []
        errors = []

        def try_execute():
            try:
                result = process.execute()
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Try to execute from multiple threads
        threads = [threading.Thread(target=try_execute) for _ in range(10)]

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
        processes = [Process("echo", f"test{i}") for i in range(20)]

        def execute_process(process):
            try:
                return process.execute().state
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
        """Test that locks don't cause deadlocks."""
        process = Process("sleep", "0.1")

        def slow_operation():
            with process.lock:
                time.sleep(0.2)

        def quick_execute():
            return process.execute()

        # Start slow operation
        slow_thread = threading.Thread(target=slow_operation)
        slow_thread.start()

        # Give it time to acquire lock
        time.sleep(0.01)

        # Try to execute - should not deadlock
        start_time = time.time()
        process.execute()
        elapsed = time.time() - start_time

        # Should complete in reasonable time (not hang due to deadlock)
        assert elapsed < 1.0

        slow_thread.join()

    def test_exception_state_consistency(self):
        """Test that state remains consistent after exceptions."""
        # Test with command that doesn't exist
        process = Process("nonexistent_command_12345")

        try:
            process.execute()
        except Exception:
            pass  # Expected to fail

        # State should be consistent (not corrupted)
        final_state = process.state
        assert isinstance(final_state, ProcessState)
        assert final_state in (ProcessState.TERMINATED, ProcessState.SPAWNING)

    def test_state_access_after_cleanup(self):
        """Test state access behavior after process completion."""
        process = Process("echo", "test")
        process.execute()

        # State should still be accessible after completion
        assert process.state == ProcessState.TERMINATED

        # Multiple accesses should work
        for _ in range(10):
            assert process.state == ProcessState.TERMINATED


class TestLockBehavior:
    """Specific tests for lock behavior and deadlock prevention."""

    def test_reentrant_lock_behavior(self):
        """Test that RLock allows re-entry by same thread."""
        process = Process("echo", "test")

        def nested_lock_usage():
            with process.lock:
                with process.lock:
                    with process.lock:
                        return process.state

        # Should not deadlock
        state = nested_lock_usage()
        assert state == ProcessState.PENDING

    def test_lock_contention_handling(self):
        """Test proper handling of lock contention."""
        process = Process("echo", "test")
        results = []

        def lock_operation(thread_id):
            with process.lock:
                time.sleep(0.01)
                results.append(thread_id)

        # Start multiple threads competing for the lock
        threads = [threading.Thread(target=lock_operation, args=(i,)) for i in range(5)]

        start_time = time.time()
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()
        elapsed = time.time() - start_time

        # All threads should complete in reasonable time
        assert len(results) == 5
        assert elapsed < 0.5  # Should not take too long
        assert sorted(results) == [0, 1, 2, 3, 4]

    def test_exception_during_lock(self):
        """Test that locks are properly released even if exception occurs."""
        process = Process("echo", "test")

        def operation_with_exception():
            try:
                with process.lock:
                    process.execute()
                    raise ValueError("Test exception")
            except ValueError:
                pass  # Expected

        thread = threading.Thread(target=operation_with_exception)
        thread.start()
        thread.join()

        # Lock should be released and process should be in consistent state
        assert process.state == ProcessState.TERMINATED
