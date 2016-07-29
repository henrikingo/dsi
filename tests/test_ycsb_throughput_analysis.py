"""Unit tests for `ycsb_throughput_analysis.py`."""

# pylint: disable=protected-access

from os import path
import unittest
import ycsb_throughput_analysis as ycsb_throughput
from tests import test_utils

class TestYCSBThroughputAnalysis(unittest.TestCase):
    """Test suite."""

    def test_get_ycsb_file_paths(self):
        """Test `_get_ycsb_file_paths()`."""

        reports_dir = test_utils.fixture_file_path("test_ycsb_throughput_analysis")
        actual_paths = ycsb_throughput._get_ycsb_file_paths(reports_dir)
        expected_files = [
            "dir2/test_screen_capture.log--ec2-userdir2",
            "dir1/test_screen_capture.log--ec2-userdir1",
            "dir3/dir4/test_screen_capture.log--ec2-user4.txt",
            "dir3/test_screen_capture.log--ec2-userdir3"]
        expected_paths = [path.join(reports_dir, "ycsb-run", fname) for fname in expected_files]
        self.assertEqual(set(actual_paths), set(expected_paths))

    def test_throughputs_from_lines(self):
        """Test `_throughputs_from_lines()`."""

        lines = [
            "not a stats line",
            " totally bad line",
            " 0 sec: 0 operations;",
            " 10 sec: 1033330 operations; 103209.15 current ops/sec; [something];;;;",
            " 20 sec: 2357178 operations; 132371.56 current ops/sec; junk data",
            "not a stats line",
            " 30 sec: 3688285 operations; 133097.39 current ops/sec;",
            " 40 sec: 5021949 operations; 133353.06 current ops/sec;",
            " 50 sec: 6355297 operations; 133321.47 current ops/sec;"]

        actual_throughputs = ycsb_throughput._throughputs_from_lines(lines)
        expected_throughputs = [
            (10.0, 103209.15),
            (20.0, 132371.56),
            (30.0, 133097.39),
            (40.0, 133353.06),
            (50.0, 133321.47)]
        self.assertEqual(actual_throughputs, expected_throughputs)

    def test_analyze_throughputs(self):
        """Test `_analyze_throughputs()`."""

        def analyze(*args, **kwargs):
            """Convenience function to reduce boilerplate when calling `_analyze_throughputs()`."""

            return ycsb_throughput._analyze_throughputs(throughputs, *args, **kwargs)[0]

        throughputs = [
            ycsb_throughput.Throughput(0, 20),
            ycsb_throughput.Throughput(10, 0),
            ycsb_throughput.Throughput(20, 0),
            ycsb_throughput.Throughput(30, 20)]
        self.assertFalse(analyze(min_duration=8, skip_initial_seconds=-1))
        self.assertFalse(analyze(min_duration=10, skip_initial_seconds=-1))
        self.assertTrue(analyze(min_duration=20, skip_initial_seconds=-1))
        self.assertTrue(analyze(min_duration=30, skip_initial_seconds=-1))

        # throughputs = [(0, 10), (10, 5), (20, 5), (30, 10)]
        throughputs = [
            ycsb_throughput.Throughput(0, 10),
            ycsb_throughput.Throughput(10, 5),
            ycsb_throughput.Throughput(20, 5),
            ycsb_throughput.Throughput(30, 10)]
        self.assertFalse(analyze(max_drop=0.8, min_duration=10, skip_initial_seconds=-1))
        self.assertTrue(analyze(max_drop=0.4, min_duration=10, skip_initial_seconds=-1))


        throughputs = [(0, 0), (5, 0), (10, 0), (20, 0), (30, 100), (40, 100)]
        throughputs = [
            ycsb_throughput.Throughput(0, 0),
            ycsb_throughput.Throughput(5, 0),
            ycsb_throughput.Throughput(10, 0),
            ycsb_throughput.Throughput(20, 0),
            ycsb_throughput.Throughput(30, 100),
            ycsb_throughput.Throughput(40, 100)]
        self.assertTrue(analyze(max_drop=0.9, min_duration=5, skip_initial_seconds=20))
        self.assertFalse(analyze(max_drop=0.9, min_duration=1, skip_initial_seconds=5))

        throughputs = [
            ycsb_throughput.Throughput(0, 10),
            ycsb_throughput.Throughput(10, 10),
            ycsb_throughput.Throughput(20, 0),
            ycsb_throughput.Throughput(30, 10)]
        self.assertTrue(analyze(max_drop=1, min_duration=1, skip_initial_seconds=-1))
