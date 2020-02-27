"""Unit tests for `log_analysis.py`."""

from __future__ import absolute_import
from os import path
import unittest

from test_lib.fixture_files import FixtureFiles
from dsi.libanalysis import log_analysis

FIXTURE_FILES = FixtureFiles(path.join(path.dirname(__file__)), "analysis")


class TestLogAnalysis(unittest.TestCase):
    """Test suite."""

    def test_get_log_file_paths(self):
        """Test `_get_bad_log_lines()`."""

        log_dir = FIXTURE_FILES.fixture_file_path("test_log_analysis")
        expected_paths = set(
            [
                path.join(log_dir, "log_subdir1/mongod.log"),
                path.join(log_dir, "log_subdir2/log_subsubdir/mongod.log"),
            ]
        )
        actual_paths = set(log_analysis._get_log_file_paths(log_dir))
        self.assertEqual(expected_paths, actual_paths)
