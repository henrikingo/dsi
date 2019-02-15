"""
Unit tests for signal_processing/detect_outliers.py.
"""

import os
import time
import unittest

from mock import MagicMock, call, patch, ANY

import signal_processing.detect_outliers as detect_outliers
from signal_processing.detect_outliers import DETECTED_TYPE, SUSPICIOUS_TYPE
from signal_processing.commands import jobs
from signal_processing.detect_outliers import main, _translate_outliers
from test_lib.fixture_files import FixtureFiles
from click.testing import CliRunner

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))

TASK_ID = 'task_id'
MONGO_URI = 'mongo_uri'
OUTLIERS_PERCENTAGE = 10
MAD = True
SIGNIFICANCE_LEVEL = 0.001

NS = 'signal_processing.detect_outliers'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


# pylint: disable=invalid-name, protected-access
class TestDetectOutliersDriver(unittest.TestCase):
    """
    Test suite for the DetectOutliersDriver class.
    """

    @classmethod
    def setUpClass(cls):
        cls.sysperf_perf_json = FIXTURE_FILES.load_json_file('sysperf_perf.json')

    @patch('multiprocessing.cpu_count', autospec=True)
    def test_constructor(self, mock_cpu_count):
        """ test outliers driver ctor. """
        mock_cpu_count.return_value = 101
        is_patch = False
        test_driver = detect_outliers.DetectOutliersDriver(self.sysperf_perf_json, MONGO_URI,
                                                           OUTLIERS_PERCENTAGE, is_patch, MAD,
                                                           SIGNIFICANCE_LEVEL)
        self.assertEquals(test_driver.pool_size, 200)

    def test_constructor_pool_size(self):
        """ test pool size. """
        is_patch = False
        test_driver = detect_outliers.DetectOutliersDriver(
            self.sysperf_perf_json,
            MONGO_URI,
            OUTLIERS_PERCENTAGE,
            is_patch,
            MAD,
            SIGNIFICANCE_LEVEL,
            pool_size=99)
        self.assertEquals(test_driver.pool_size, 99)

    def test_run(self):
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
            is_patch = False
            test_driver = detect_outliers.DetectOutliersDriver(self.sysperf_perf_json, MONGO_URI,
                                                               OUTLIERS_PERCENTAGE, is_patch, MAD,
                                                               SIGNIFICANCE_LEVEL)
            test_driver.run()
            mock_PointsModel.assert_called_once_with(MONGO_URI)

            calls = [
                call(
                    detect_outliers._get_data_and_run_detection,
                    arguments=(mock_model, test_identifier, self.sysperf_perf_json['order'],
                               OUTLIERS_PERCENTAGE, is_patch, MAD, SIGNIFICANCE_LEVEL),
                    identifier=test_identifier) for test_identifier in test_identifiers
            ]
            mock_job_cls.assert_has_calls(calls)


class TestDetectOutliers(unittest.TestCase):
    # pylint: disable=no-self-use
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
        is_patch = False
        detect_outliers.detect_outliers(task_id, MONGO_URI, OUTLIERS_PERCENTAGE, is_patch, MAD,
                                        SIGNIFICANCE_LEVEL, pool_size, progressbar)

        mock_driver.assert_called_once_with(
            mock_perf_json,
            MONGO_URI,
            OUTLIERS_PERCENTAGE,
            is_patch,
            MAD,
            SIGNIFICANCE_LEVEL,
            pool_size=pool_size,
            progressbar=progressbar)
        mock_runner.run.assert_called_once()


class TestRunDetection(unittest.TestCase):
    # pylint: disable=protected-access, too-many-locals
    """
    Test suite for the detect_outliers function.
    """

    @classmethod
    def setUpClass(cls):
        file_parts = [
            'sys-perf', 'linux-1-node-replSet', 'bestbuy_query', 'canary_client-cpuloop-10x', '1'
        ] + ['{}.json'.format('standard')]

        filename = os.path.join(*file_parts)
        cls.fixture = FIXTURE_FILES.load_json_file(filename)
        cls.expected = cls.fixture['expected']
        cls.data = cls.fixture['data']

    def test_detect_outliers(self):
        """
        Test detect_outliers.detect_outliers function.
        """

        is_patch = False
        with patch(ns('Outlier'), autospec=True) as mock_outlier_ctor,\
             patch(ns('pymongo.InsertOne'), autospec=True) as mock_insert,\
             patch(ns('pymongo.DeleteMany'), autospec=True) as mock_delete,\
             patch(ns('get_change_point_range'), autospec=True) as mock_get_change_point_range:

            mock_points_model = MagicMock()
            # for test in (u'mixed_insert', u'mixed_insert_bad', u'mixed_findOne')]
            times_series = self.data['time_series']
            test_identifier = {
                'project': times_series['project'],
                'variant': times_series['variant'],
                'task': times_series['task'],
                'test': times_series['test'],
                'thread_level': times_series['thread_level'],
            }

            start_order = self.data['start_order']
            end_order = self.data['end_order']
            start = times_series['orders'].index(start_order)
            end = times_series['orders'].index(end_order)
            series = times_series['series'][start:end]

            expected_suspicious_indexes = self.expected['suspicious_indexes']

            mock_get_change_point_range.return_value = (start, end, series)

            expected_range = list(range(len(expected_suspicious_indexes)))
            mock_points_model.get_points.return_value = times_series
            mock_outlier_ctor.return_value._asdict.side_effect = expected_range
            deletes = ['delete']
            inserts = ['insert {}'.format(i) for i in expected_range]
            requests = deletes + inserts

            mock_delete.side_effect = deletes
            mock_insert.side_effect = inserts

            mock_client = mock_points_model.db.client
            mock_session = mock_client.start_session.return_value.__enter__.return_value
            mock_outliers_collection = mock_points_model.db.__getitem__.return_value

            outliers_percentage = OUTLIERS_PERCENTAGE / 100.0
            outlier_results = detect_outliers._get_data_and_run_detection(
                mock_points_model, test_identifier, start_order, outliers_percentage, is_patch, MAD,
                SIGNIFICANCE_LEVEL)

            mock_outliers_collection.bulk_write.assert_called_once_with(requests)
            mock_client.start_session.assert_called_once()
            mock_session.start_transaction.return_value.__enter__.assert_called_once()

            gesd_result = outlier_results.gesd_result
            self.assertEquals(gesd_result.count, self.expected['number_outliers'])
            self.assertListEqual(gesd_result.suspicious_indexes, expected_suspicious_indexes)

            mock_delete.assert_called_once()
            mock_insert.assert_has_calls([call(i) for i in expected_range])

            count = gesd_result.count
            mock_outlier_ctor.assert_has_calls([
                call(
                    type=DETECTED_TYPE if pos < count else SUSPICIOUS_TYPE,
                    project=ANY,
                    variant=ANY,
                    task=ANY,
                    test=ANY,
                    thread_level=ANY,
                    revision=ANY,
                    task_id=ANY,
                    version_id=ANY,
                    order=ANY,
                    create_time=ANY,
                    change_point_revision=ANY,
                    change_point_order=ANY,
                    order_of_outlier=ANY,
                    z_score=ANY,
                    critical_value=ANY,
                    mad=ANY,
                    significance_level=ANY,
                    num_outliers=ANY) for pos, _ in enumerate(expected_suspicious_indexes)
            ])


class TestTranslateOutliers(unittest.TestCase):
    """
    Test suite for the _save_outliers function
    """

    def test_no_gesd_results(self):
        outliers = _translate_outliers(None, {}, 0, False, 0.1, 5, {})
        self.assertEqual(0, len(outliers))

    def test_gesd_count_of_zero(self):
        gesd_results = MagicMock(count=0)
        outliers = _translate_outliers(gesd_results, {}, 0, False, 0.1, 5, {})
        self.assertEqual(0, len(outliers))


class TestMain(unittest.TestCase):
    # pylint: disable=unused-argument
    """
    Test suite for the main function.
    """

    def setUp(self):
        self.config = {'runtime': {'task_id': 'tid', }, 'analysis': {'mongo_uri': 'muri'}}
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
    def test_is_patch(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test this is a patch.
        """
        is_patch = True
        mock_detect_outliers.return_value = None
        mock_config = mock_config_dict.return_value
        self.config['runtime']['is_patch'] = is_patch
        mock_config.__getitem__.side_effect = self.config.__getitem__

        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(False, filename='detect_outliers.log')
        mock_detect_outliers.assert_called_once_with(
            'tid', 'muri', 0, is_patch, False, 0.05, None, progressbar=False)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    def test_defaults(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test default params.
        """
        is_patch = False
        mock_detect_outliers.return_value = None
        mock_config = mock_config_dict.return_value
        mock_config.__getitem__.side_effect = self.config.__getitem__

        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(False, filename='detect_outliers.log')
        mock_detect_outliers.assert_called_once_with(
            'tid', 'muri', 0, is_patch, False, 0.05, None, progressbar=False)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    def test_params(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test main with params.
        """
        is_patch = False
        mock_detect_outliers.return_value = None
        mock_config = mock_config_dict.return_value
        mock_config.__getitem__.side_effect = self.config.__getitem__

        result = self.runner.invoke(main, [
            '-l', 'logfile', '--pool-size', '1', '--max-outliers', '0.40', '--mad',
            '--significance', '0.20', '--progressbar', '-v'
        ])
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(True, filename='logfile')
        mock_detect_outliers.assert_called_once_with(
            'tid', 'muri', 0.40, is_patch, True, 0.2, 1, progressbar=True)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    def test_outliers_0(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test main with params.
        """
        is_patch = False
        mock_detect_outliers.return_value = None
        mock_config = mock_config_dict.return_value
        mock_config.__getitem__.side_effect = self.config.__getitem__

        result = self.runner.invoke(main, [
            '-l', 'logfile', '--pool-size', '1', '--max-outliers', '0', '--mad', '--significance',
            '0.20', '--progressbar', '-v'
        ])
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(True, filename='logfile')
        mock_detect_outliers.assert_called_once_with(
            'tid', 'muri', .0, is_patch, True, 0.2, 1, progressbar=True)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    def test_outliers_too_large(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test main with outliers gt 1.
        """
        mock_detect_outliers.return_value = None
        mock_config = mock_config_dict.return_value
        mock_config.__getitem__.side_effect = self.config.__getitem__

        result = self.runner.invoke(main, [
            '-l', 'logfile', '--pool-size', '1', '--max-outliers', '1.40', '--mad',
            '--significance', '0.20', '--progressbar', '-v'
        ])
        self.assertEqual(result.exit_code, 2)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    def test_outliers_too_small(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test main with outliers lt 0.
        """
        mock_detect_outliers.return_value = None
        mock_config = mock_config_dict.return_value
        mock_config.__getitem__.side_effect = self.config.__getitem__

        result = self.runner.invoke(main, [
            '-l', 'logfile', '--pool-size', '1', '--max-outliers', '-1.40', '--mad',
            '--significance', '0.20', '--progressbar', '-v'
        ])
        self.assertEqual(result.exit_code, 2)

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
    """
    Test Get change point range function.
    """

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
        """ test after last range. """
        self._test(102, 90, 100)

    def test_in_last_range(self):
        """ test last range. """
        self._test(93, 90, 100)

    def test_in_middle_range(self):
        """ test middle of range. """
        self._test(77, 70, 80)

    def test_in_first_range(self):
        """ test in first range. """
        self._test(9, 0, 10)

    def test_before_first_range(self):
        """ test before range. """
        self._test(-9, 0, 10)

    def test_is_change_point(self):
        """ test with change points. """
        self._test(20, 20, 30)

    def test_no_change_points(self):
        """ test no change points. """
        mock_model = MagicMock()
        mock_collection = mock_model.db.get_collection.return_value
        mock_collection.find.return_value.sort.return_value = []

        start, end, series = detect_outliers.get_change_point_range(mock_model, 'id',
                                                                    self.full_series, 13)

        self.assertEqual(0, start)
        self.assertEqual(100, end)
        self.assertListEqual(self.full_series['series'][start:end], series)
