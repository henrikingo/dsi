"""Tests for bin/process_fio_results.py"""

import os.path
import unittest

import process_fio_results as pr


class TestProcessFIOResults(unittest.TestCase):
    ''' Test process_fio_results.py'''

    def setUp(self):
        ''' Setup basic environment '''
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.artifact_dir = os.path.join(self.test_dir, 'artifacts')
        self.input_file = os.path.join(self.artifact_dir, 'fio.json')

    def test_format_result(self):
        ''' Test the format_result function '''
        self.assertEqual(pr.format_result(None, 'job', 'read', 'test', 1.25),
                         '>>> job_read_test :         1.25 1')
        self.assertEqual(pr.format_result('fio', 'job', 'read', 'test', 1.25),
                         '>>> fio_job_read_test :         1.25 1')
        self.assertEqual(pr.format_result('fio', 'job', 'read', 'test', 1.25, 2),
                         '>>> fio_job_read_test :         1.25 2')

    def test_process_results_for_mc(self):
        ''' Test process_results_for_mc '''
        # Use fio.json that's saved
        # Compare to saved output.
        output = pr.process_results_for_mc(filename=self.input_file)
        with open(os.path.join(self.artifact_dir, 'fio.json.processed')) as expected_file:
            expected = expected_file.readlines()
        expected = [line.rstrip() for line in expected]
        self.assertEqual(output, expected)

    def test_filter_results(self):
        ''' Test filter_results'''
        # Run simple output through it.
        with open(os.path.join(self.artifact_dir, 'fio.json.processed')) as input_file:
            input_lines = input_file.readlines()
        with open(os.path.join(self.artifact_dir, 'fio.json.processed.short')) as input_file:
            expected = input_file.readlines()
        expected = [line.rstrip() for line in expected]
        input_lines = [line.rstrip() for line in input_lines]
        output = pr.filter_results(input_lines)
        self.assertEqual(output, expected)
