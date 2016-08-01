"""Unit tests for `log_analysis.py`."""

# pylint: disable=protected-access

from os import path
import unittest
import datetime
from dateutil import parser as date_parser

import log_analysis
from tests import test_utils

class TestLogAnalysis(unittest.TestCase):
    """Test suite."""

    def test_is_log_line_bad(self):
        """Test `_is_log_line_bad()`."""

        bad_lines = [
            "2016-07-14T01:00:04.000+0000 F err-type foo bar baz",
            "2016-07-14T01:00:04.000+0000 E err-type foo bar baz",
            "2016-07-14T01:00:04.000+0000 L err-type elecTIon suCCEeded",
            "2016-07-14T01:00:04.000+0000 D err-type transition TO PRIMARY"]

        good_lines = [
            "2016-07-14T01:00:04.000+0000 L err-type nothing bad here",
            "2016-07-14T01:00:04.000+0000 L err-type or here"]

        for line in bad_lines:
            self.assertTrue(log_analysis._is_log_line_bad(line))

        for line in good_lines:
            self.assertFalse(log_analysis._is_log_line_bad(line))

    def test_is_log_line_bad_time(self):
        """Test `_is_log_line_bad()` when test times are specified."""

        test_times = [
            (date_parser.parse("2016-07-14T01:00:00.000+0000"),
             date_parser.parse("2016-07-14T01:10:00.000+0000")),
            (date_parser.parse("2016-07-14T03:00:00.000+0000"),
             date_parser.parse("2016-07-14T03:10:00.000+0000"))]

        bad_lines = [
            "2016-07-14T01:00:04.000+0000 F err-type message",
            "2016-07-14T01:09:00.000+0000 F err-type message",
            "2016-07-14T03:05:00.000+0000 F err-type message"]

        bad_lines_to_ignore = [
            "2016-07-14T00:05:00.000+0000 F err-type message",
            "2016-07-14T02:00:00.000+0000 F err-type message",
            "2016-07-14T03:25:00.000+0000 F err-type message"]

        for line in bad_lines:
            self.assertTrue(log_analysis._is_log_line_bad(line, test_times))

        for line in bad_lines_to_ignore:
            self.assertFalse(log_analysis._is_log_line_bad(line, test_times))

    def test_get_log_file_paths(self):
        """Test `_get_bad_log_lines()`."""

        log_dir = test_utils.fixture_file_path("test_log_analysis")
        expected_paths = set([
            path.join(log_dir, "log_subdir1/mongod.log"),
            path.join(log_dir, "log_subdir2/log_subsubdir/mongod.log")])
        actual_paths = set(log_analysis._get_log_file_paths(log_dir))
        self.assertEqual(expected_paths, actual_paths)

    def test_num_or_str_to_date(self):
        """Test `_num_or_str_to_date()`."""

        self.assertIsInstance(log_analysis._num_or_str_to_date(1), datetime.datetime)
        parsed_date = log_analysis._num_or_str_to_date("2016-07-14T03:25:00.000+0000")
        self.assertIsInstance(parsed_date, datetime.datetime)

    def test_get_test_times(self):
        """Test `_get_test_times()`."""

        def assert_instancesof_datetime(tuples):
            """
            Assert that all of the items in a list of tuples are instanced of
            `datetime.datetime`.
            """

            for pair in tuples:
                for item in pair:
                    self.assertIsInstance(item, datetime.datetime)

        perf_json = {
            "results": [],
            "start": "2016-07-14T03:25:00.000+0000",
            "end": "2016-07-14T03:24:00.000+0000"
        }
        times = log_analysis._get_test_times(perf_json)
        self.assertEqual(len(times), 1)
        assert_instancesof_datetime(times)

        perf_json = {
            "results": [
                {"start": 1, "end": 2},
                {"start": 3, "end": 4},
                {"start": 5, "end": "2016-07-14T03:24:00.000+0000"}
            ]
        }
        times = log_analysis._get_test_times(perf_json)
        self.assertEqual(len(times), 3)
        assert_instancesof_datetime(times)
