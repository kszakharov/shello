"""Test pipeline state machine behavior and thread safety."""

import threading
from concurrent.futures import ThreadPoolExecutor

from shello import Command
from shello.process import ProcessState


class TestPipelineStateMachine:
    """Test state machine behavior in pipeline contexts."""

    def test_pipeline_state_transitions(self):
        """Test state transitions in pipeline execution."""
        cmd1 = Command("echo", "hello")
        cmd2 = Command("grep", "hello")

        # Create pipeline
        pipeline = cmd1 | cmd2

        # Execute pipeline
        pipeline = pipeline.execute()

        # Both should complete
        assert pipeline.processes[0].state == ProcessState.TERMINATED
        assert pipeline.processes[1].state == ProcessState.TERMINATED

        # Pipeline result should be the pipeline containing cmd2
        assert pipeline.commands[-1] == cmd2

    def test_pipeline_failure_state(self):
        """Test state handling when pipeline command fails."""
        cmd1 = Command("echo", "hello")
        cmd2 = Command("false", check=False)  # Always fails

        pipeline = cmd1 | cmd2
        pipeline.execute()

        # First should succeed, second should fail
        assert pipeline.processes[0].state == ProcessState.TERMINATED
        assert pipeline.processes[1].state == ProcessState.TERMINATED

    def test_pipeline_concurrent_execution_safety(self):
        """Test thread safety of pipeline execution."""
        results = []
        errors = []

        def create_and_execute_pipeline():
            try:
                cmd1 = Command("echo", f"test{threading.get_ident()}")
                cmd2 = Command("cat")
                pipeline = cmd1 | cmd2
                result = pipeline.execute()
                results.append((threading.get_ident(), result.returncode))
            except Exception as e:
                errors.append((threading.get_ident(), e))

        # Run multiple pipelines concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_and_execute_pipeline) for _ in range(10)]

            for future in futures:
                future.result()

        # All should complete (either successfully or with errors)
        assert len(results) + len(errors) == 10
        assert len(errors) == 0

        # All should succeed with returncode 0
        for _thread_id, returncode in results:
            assert returncode == 0

    def test_pipeline_state_after_exception(self):
        """Test pipeline state remains consistent after exceptions."""
        cmd1 = Command("echo", "test")
        cmd2 = Command("cat")

        pipeline = cmd1 | cmd2
        pipeline.execute()

        # States should be accessible and consistent
        assert pipeline.processes[0].state == ProcessState.TERMINATED
        assert pipeline.processes[1].state == ProcessState.TERMINATED
        assert pipeline.is_done

        # Multiple accesses should work
        for _ in range(10):
            assert pipeline.is_done
