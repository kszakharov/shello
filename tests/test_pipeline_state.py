"""Test pipeline state machine behavior and thread safety."""

import threading
from concurrent.futures import ThreadPoolExecutor

from shello import Process
from shello.process import ProcessState


class TestPipelineStateMachine:
    """Test state machine behavior in pipeline contexts."""

    def test_pipeline_state_transitions(self):
        """Test state transitions in pipeline execution."""
        cmd1 = Process("echo", "hello")
        cmd2 = Process("grep", "hello")

        # Create pipeline
        pipeline = cmd1 | cmd2

        # Both should start in PENDING
        assert cmd1.state == ProcessState.PENDING
        assert cmd2.state == ProcessState.PENDING

        # Execute pipeline
        result = pipeline.execute()

        # Both should complete
        assert cmd1.state == ProcessState.TERMINATED
        assert cmd2.state == ProcessState.TERMINATED

        # Pipeline result should be the pipeline containing cmd2
        assert result.processes[-1] == cmd2

    def test_pipeline_failure_state(self):
        """Test state handling when pipeline command fails."""
        cmd1 = Process("echo", "hello")
        cmd2 = Process("false", check=False)  # Always fails

        pipeline = cmd1 | cmd2
        pipeline.execute()

        # First should succeed, second should fail
        assert cmd1.state == ProcessState.TERMINATED
        assert cmd2.state == ProcessState.TERMINATED

    def test_pipeline_concurrent_execution_safety(self):
        """Test thread safety of pipeline execution."""
        results = []
        errors = []

        def create_and_execute_pipeline():
            try:
                cmd1 = Process("echo", f"test{threading.get_ident()}")
                cmd2 = Process("cat")
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
        cmd1 = Process("echo", "test")
        cmd2 = Process("cat")

        pipeline = cmd1 | cmd2
        pipeline.execute()

        # States should be accessible and consistent
        assert cmd1.state == ProcessState.TERMINATED
        assert cmd2.state == ProcessState.TERMINATED
        assert pipeline.is_terminated

        # Multiple accesses should work
        for _ in range(10):
            assert pipeline.is_terminated
