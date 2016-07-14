"""
Unit tests for `log_analysis.py`.
"""

from os import path
import unittest
import log_analysis
from tests import test_utils

class TestCompare(unittest.TestCase):
    """Test suite."""

    def test_is_log_line_bad(self): # pylint: disable=protected-access
        """
        Test `_is_log_line_bad()`.
        """

        bad_lines = [
            "timestamp F err-type foo bar baz",
            "timestamp E err-type foo bar baz",
            "timestamp L err-type elecTIon suCCEeded",
            "timestamp D err-type transition TO PRIMARY"]

        good_lines = [
            "timestamp L err-type nothing bad here",
            "timestamp L err-type or here"]

        # pylint: disable=protected-access
        for line in bad_lines:
            self.assertTrue(log_analysis._is_log_line_bad(line))

        for line in good_lines:
            self.assertFalse(log_analysis._is_log_line_bad(line))

    def test_get_log_file_paths(self):
        """
        Test `_get_bad_log_lines()`.
        """

        log_dir = test_utils.fixture_file_path("test_log_analysis")
        expected_paths = set([
            path.join(log_dir, "log_subdir1/mongod.log"),
            path.join(log_dir, "log_subdir2/log_subsubdir/mongod.log")])
        actual_paths = set(log_analysis._get_log_file_paths(log_dir)) # pylint: disable=protected-access
        self.assertEqual(expected_paths, actual_paths)
