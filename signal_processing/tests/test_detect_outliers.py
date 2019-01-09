"""
Unit tests for signal_processing/detect_outliers.py.
"""

import os
import time
import unittest

from mock import MagicMock, call, patch

import signal_processing.detect_outliers as detect_outliers
from signal_processing.commands import jobs
from signal_processing.detect_outliers import main
from test_lib.fixture_files import FixtureFiles
from click.testing import CliRunner

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))

TASK_ID = 'task_id'
MONGO_URI = 'mongo_uri'
MAX_OUTLIERS = 10
MAD = True
SIGNIFICANCE_LEVEL = 0.001

NS = 'signal_processing.detect_outliers'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


# pylint: disable=invalid-name
class TestDetectOutliersDriver(unittest.TestCase):
    """
    Test suite for the DetectOutliersDriver class.
    """

    @classmethod
    def setUpClass(cls):
        cls.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf.json')

    @patch('multiprocessing.cpu_count', autospec=True)
    def test_constructor(self, mock_cpu_count):
        mock_cpu_count.return_value = 101
        test_driver = detect_outliers.DetectOutliersDriver(self.sysperf_perf_json, MONGO_URI,
                                                           MAX_OUTLIERS, MAD, SIGNIFICANCE_LEVEL)
        self.assertEquals(test_driver.pool_size, 200)

    def test_constructor_pool_size(self):
        test_driver = detect_outliers.DetectOutliersDriver(
            self.sysperf_perf_json, MONGO_URI, MAX_OUTLIERS, MAD, SIGNIFICANCE_LEVEL, pool_size=99)
        self.assertEquals(test_driver.pool_size, 99)

    def _test_run(self):
        """ test run. """

        with patch(ns('multiprocessing.cpu_count'), autospec=True) as mock_cpu_count, \
             patch(ns('jobs.Job'), autospec=True) as mock_job_cls,\
             patch(ns('jobs.process_jobs'), autospec=True) as mock_process_jobs,\
             patch(ns('detect_changes.PointsModel'), autospec=True) as mock_PointsModel:

            mock_job = MagicMock(name='mock_job')
            mock_job_cls.return_value = mock_job

            mock_process_jobs.return_value = ()
            mock_cpu_count.return_value = 101
            mock_model = mock_PointsModel.return_value

            test_identifiers = [{
                'project': self.sysperf_perf_json['project_id'],
                'variant': self.sysperf_perf_json['variant'],
                'task': self.sysperf_perf_json['task_name'],
                'test': test,
                'thread_level': '1'
            } for test in (u'mixed_insert', u'mixed_insert_bad', u'mixed_findOne')]

            mock_model.db.points.aggregate.return_value = test_identifiers
            test_driver = detect_outliers.DetectOutliersDriver(
                self.sysperf_perf_json, MONGO_URI, MAX_OUTLIERS, MAD, SIGNIFICANCE_LEVEL)
            test_driver.run()
            mock_PointsModel.assert_called_once_with(MONGO_URI)

            calls = [
                call(
                    detect_outliers._get_data_and_run_detection,
                    arguments=(mock_model, test_identifier, MAX_OUTLIERS, MAD, SIGNIFICANCE_LEVEL),
                    identifier=test_identifier) for test_identifier in test_identifiers
            ]
            mock_job_cls.assert_has_calls(calls)


class TestDetectOutliers(unittest.TestCase):
    """
    Test suite for the detect_outliers function.
    """

    @patch(ns('evergreen_client.Client'), autospec=True)
    @patch(ns('DetectOutliersDriver'), autospec=True)
    def test_detect_outliers(self, mock_driver, mock_evg_cl):
        """
        Test detect_outliers.detect_outliers function.
        """
        task_id = 'task_id'
        pool_size = 7
        progressbar = True

        mock_perf_json = MagicMock()
        mock_evg_client = mock_evg_cl.return_value
        mock_evg_client.query_perf_results.return_value = mock_perf_json
        mock_runner = mock_driver.return_value
        detect_outliers.detect_outliers(task_id, MONGO_URI, MAX_OUTLIERS, MAD, SIGNIFICANCE_LEVEL,
                                        pool_size, progressbar)

        mock_driver.assert_called_once_with(
            mock_perf_json,
            MONGO_URI,
            MAX_OUTLIERS,
            MAD,
            SIGNIFICANCE_LEVEL,
            pool_size=pool_size,
            progressbar=progressbar)
        mock_runner.run.assert_called_once()


class TestMain(unittest.TestCase):
    """
    Test suite for the main function.
    """

    @classmethod
    def setUpClass(cls):
        cls.config = {'runtime': {'task_id': 'tid', }, 'analysis': {'mongo_uri': 'muri'}}

    def setUp(self):
        self.runner = CliRunner()

    @patch(ns('detect_outliers'))
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'))
    def test_help(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test main responds to help.
        """
        result = self.runner.invoke(main, ['help'])
        self.assertEqual(result.exit_code, 2)

        mock_logging.assert_not_called()
        mock_config_dict.assert_not_called()
        mock_detect_outliers.assert_not_called()

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    def test_defaults(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test default params.
        """
        mock_detect_outliers.return_value = None
        mock_config = mock_config_dict.return_value
        mock_config.__getitem__.side_effect = self.config.__getitem__

        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(False, filename='detect_outliers.log')
        mock_detect_outliers.assert_called_once_with(
            'tid', 'muri', 0, False, 0.05, None, progressbar=False)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    def test_params(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test main with params.
        """
        mock_detect_outliers.return_value = None
        mock_config = mock_config_dict.return_value
        mock_config.__getitem__.side_effect = self.config.__getitem__

        result = self.runner.invoke(main, [
            '-l', 'logfile', '--pool-size', '1', '--max_outliers', '7000', '--mad',
            '--significance', '0.20', '--progressbar', '-v'
        ])
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(True, filename='logfile')
        mock_detect_outliers.assert_called_once_with(
            'tid', 'muri', 7000, True, 0.2, 1, progressbar=True)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'))
    def test_exception(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test main handles errors.
        """
        mock_detect_outliers.return_value = (jobs.Job(time.sleep), )
        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 2)
        self.assertIn('1 Unexpected Exceptions', result.output)

        mock_logging.assert_called_once()
        mock_config_dict.assert_called_once()


class TestGetChangePointRange(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full_series = {
            'orders': [i for i in range(100)],
            'series': ['s%d' % i for i in range(100)]
        }
        cls.mock_model = MagicMock()
        mock_collection = cls.mock_model.db.get_collection.return_value
        # First change point is 10 and last change point is 90.
        mock_collection.find.return_value.sort.return_value = [{
            'order': i
        } for i in range(90, 0, -10)]

    def _test(self, order, expected_start, expected_end):
        start, end, series = detect_outliers.get_change_point_range(self.mock_model, 'id',
                                                                    self.full_series, order)

        self.assertEqual(expected_start, start)
        self.assertEqual(expected_end, end)
        self.assertListEqual(self.full_series['series'][start:end], series)

    def test_after_last_range(self):
        self._test(102, 90, 100)

    def test_in_last_range(self):
        self._test(93, 90, 100)

    def test_in_middle_range(self):
        self._test(77, 70, 80)

    def test_in_first_range(self):
        self._test(9, 0, 10)

    def test_before_first_range(self):
        self._test(-9, 0, 10)

    def test_is_change_point(self):
        self._test(20, 20, 30)

    def test_no_change_points(self):
        mock_model = MagicMock()
        mock_collection = mock_model.db.get_collection.return_value
        mock_collection.find.return_value.sort.return_value = []

        start, end, series = detect_outliers.get_change_point_range(mock_model, 'id',
                                                                    self.full_series, 13)

        self.assertEqual(0, start)
        self.assertEqual(100, end)
        self.assertListEqual(self.full_series['series'][start:end], series)
