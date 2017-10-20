"""Unit tests for `log_analysis.py`."""

from os import path
import unittest

import log_analysis
from tests import test_utils

# pylint: disable=protected-access


class TestLogAnalysis(unittest.TestCase):
    """Test suite."""

    def test_get_log_file_paths(self):
        """Test `_get_bad_log_lines()`."""

        log_dir = test_utils.fixture_file_path("test_log_analysis")
        expected_paths = set([
            path.join(log_dir, "log_subdir1/mongod.log"),
            path.join(log_dir, "log_subdir2/log_subsubdir/mongod.log")
        ])
        actual_paths = set(log_analysis._get_log_file_paths(log_dir))
        self.assertEqual(expected_paths, actual_paths)
