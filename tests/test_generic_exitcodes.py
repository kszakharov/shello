"""Test generic iterable support for exit codes."""

from shello import Process


class TestExitCodesGeneric:
    """Test cases for generic iterable support for exit codes."""

    def test_list_acceptable_exit_codes(self):
        """Test list as acceptable exit codes (generic iterable support)."""
        process = Process("sh", "-c", "exit 7", ok_exitcodes=[5, 6, 7])
        result = process.execute()

        assert result.returncode == 7
        assert result.stdout == ""
        assert result.stderr == ""

    def test_set_acceptable_exit_codes(self):
        """Test set as acceptable exit codes (generic iterable support)."""
        process = Process("sh", "-c", "exit 3", ok_exitcodes={1, 2, 3})
        result = process.execute()

        assert result.returncode == 3
        assert result.stdout == ""
        assert result.stderr == ""

    def test_int_to_tuple_conversion(self):
        """Test that single int gets converted to tuple internally."""
        process = Process("sh", "-c", "exit 1", ok_exitcodes=1)
        result = process.execute()

        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr == ""
        # Verify internal conversion happened
        assert process.ok_exitcodes == (1,)
