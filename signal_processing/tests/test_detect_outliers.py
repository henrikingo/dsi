"""
Unit tests for signal_processing/detect_outliers.py.
"""

import os
import unittest
from collections import OrderedDict

import pymongo
from mock import MagicMock, call, patch, ANY, mock_open

import signal_processing.detect_outliers as detect_outliers
from signal_processing.commands.helpers import get_query_for_points
from signal_processing.detect_outliers import DETECTED_TYPE, SUSPICIOUS_TYPE
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

    def test_no_results(self):
        """ test handling no data (usually a system failure) """
        # pylint: disable=too-many-locals
        task_id = 'task_id'
        pool_size = 7
        progressbar = True

        is_patch = False
        rejects_file = 'rejects.json'
        max_consecutive_rejections = 3
        minimum_points = 15
        with patch(ns('evergreen_client.Client'), autospec=True),\
             patch(ns('helpers.extract_test_identifiers')) as mock_extract_test_identifiers:

            mock_extract_test_identifiers.return_value = []
            completed_jobs = detect_outliers.detect_outliers(
                task_id, MONGO_URI, OUTLIERS_PERCENTAGE, is_patch, MAD, SIGNIFICANCE_LEVEL,
                pool_size, rejects_file, max_consecutive_rejections, minimum_points, progressbar)
            self.assertListEqual([], completed_jobs)

    def _test(self, mock_driver, mock_evg_cl, successful_jobs=None):
        # pylint: disable=too-many-locals
        task_id = 'task_id'
        pool_size = 7
        progressbar = True

        if successful_jobs is None:
            successful_jobs = []

        mock_perf_json = MagicMock()
        mock_evg_client = mock_evg_cl.return_value
        mock_evg_client.query_perf_results.return_value = mock_perf_json
        mock_runner = mock_driver.return_value
        is_patch = False
        rejects_file = 'rejects.json'
        max_consecutive_rejections = 3
        minimum_points = 15

        status = {"failures": 0}
        mock_evg_client.query_task_status.return_value = status
        mock_runner.run.return_value = successful_jobs
        project = 'sys-perf'
        variant = 'linux-standalone'
        task = 'insert-remove'

        with patch(ns('write_rejects')) as mock_write_rejects, \
             patch(ns('load_status_report')) as mock_load, \
             patch(ns('TaskAutoRejector')) as mock_task_rejector_clazz, \
             patch(ns('get_updates')) as mock_get_updates, \
             patch(ns('update_outlier_status')) as mock_update_outlier_status, \
             patch(ns('helpers.extract_test_identifiers')) as mock_extract_test_identifiers:
            mock_extract_test_identifiers.return_value = [{
                'project': project,
                'variant': variant,
                'task': task
            }]
            mock_load.return_value = status
            detect_outliers.detect_outliers(task_id, MONGO_URI, OUTLIERS_PERCENTAGE, is_patch, MAD,
                                            SIGNIFICANCE_LEVEL, pool_size, rejects_file,
                                            max_consecutive_rejections, minimum_points, progressbar)

        mock_load.assert_called_once()
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
        if mock_runner.run.return_value:
            mock_task_rejector = mock_task_rejector_clazz.return_value

            rejects = mock_task_rejector_clazz.return_value.filtered_rejects.return_value

            mock_task_rejector_clazz.assert_called_once_with(
                ['result'], project, variant, task, mock_perf_json.__getitem__.return_value,
                MONGO_URI, is_patch, status, max_consecutive_rejections, minimum_points)
            mock_get_updates.assert_called_once_with(mock_task_rejector)
            mock_update_outlier_status.assert_called_once_with(mock_task_rejector.model,
                                                               mock_get_updates.return_value)
        else:
            rejects = []
        mock_write_rejects.assert_called_once_with(rejects, rejects_file)

    @patch(ns('evergreen_client.Client'), autospec=True)
    @patch(ns('DetectOutliersDriver'), autospec=True)
    def test_detect_outliers(self, mock_driver, mock_evg_cl):
        """
        Test detect_outliers.detect_outliers function.
        """
        self._test(mock_driver, mock_evg_cl)

    @patch(ns('evergreen_client.Client'), autospec=True)
    @patch(ns('DetectOutliersDriver'), autospec=True)
    def test_reject(self, mock_driver, mock_evg_cl):
        """
        Test detect_outliers.detect_outliers rejection functionality.
        """
        successful_jobs = [MagicMock(name='success', exception=False, result='result')]
        self._test(mock_driver, mock_evg_cl, successful_jobs)


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
        mock_detect_outliers.return_value = []
        mock_config = mock_config_dict.return_value
        self.config['runtime']['is_patch'] = is_patch
        mock_config.__getitem__.side_effect = self.config.__getitem__

        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(False, filename='detect_outliers.log')

        rejects_file = 'rejects.json'
        max_consecutive_rejections = 3
        minimum_points = 15

        mock_detect_outliers.assert_called_once_with(
            'tid',
            'muri',
            0,
            is_patch,
            False,
            0.05,
            None,
            rejects_file,
            max_consecutive_rejections,
            minimum_points,
            progressbar=False)

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
        mock_detect_outliers.return_value = []

        result = self.runner.invoke(main)
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(False, filename='detect_outliers.log')
        rejects_file = 'rejects.json'
        max_consecutive_rejections = 3
        minimum_points = 15

        mock_detect_outliers.assert_called_once_with(
            'tid',
            'muri',
            0,
            is_patch,
            False,
            0.05,
            None,
            rejects_file,
            max_consecutive_rejections,
            minimum_points,
            progressbar=False)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    def test_params(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test main with params.
        """
        is_patch = False
        mock_detect_outliers.return_value = []
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
        rejects_file = 'rejects.json'
        max_consecutive_rejections = 3
        minimum_points = 15

        mock_detect_outliers.assert_called_once_with(
            'tid',
            'muri',
            0.40,
            is_patch,
            True,
            0.2,
            1,
            rejects_file,
            max_consecutive_rejections,
            minimum_points,
            progressbar=True)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    def test_outliers_0(self, mock_logging, mock_config_dict, mock_detect_outliers):
        """
        Test main with params.
        """
        is_patch = False
        mock_detect_outliers.return_value = []
        mock_config = mock_config_dict.return_value
        mock_config.__getitem__.side_effect = self.config.__getitem__

        rejects_file = 'watch.json'
        max_consecutive_rejections = 5
        minimum_points = 10
        result = self.runner.invoke(main, [
            '-l', 'logfile', '--pool-size', '1', '--max-outliers', '0', '--mad', '--significance',
            '0.20', '--progressbar', '-v', '--rejects-file', rejects_file, '--rejections',
            str(max_consecutive_rejections), '--minimum',
            str(minimum_points)
        ])
        self.assertEqual(result.exit_code, 0)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(True, filename='logfile')

        mock_detect_outliers.assert_called_once_with(
            'tid',
            'muri',
            0,
            is_patch,
            True,
            0.2,
            1,
            rejects_file,
            max_consecutive_rejections,
            minimum_points,
            progressbar=True)
        # mock_detect_outliers.assert_called_once_with(
        #     'tid', 'muri', .0, is_patch, True, 0.2, 1, progressbar=True)

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
        # mock_detect_outliers.return_value = (jobs.Job(time.sleep), )
        mock_detect_outliers.return_value = (MagicMock(name='job', exception=Exception()), )
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


class TestTranslateFieldName(unittest.TestCase):
    """
    Test suite for the translate_field_name.
    """

    def test_max(self):
        """ test max. """
        self.assertEquals('test', detect_outliers.translate_field_name('test', True))

    def test_not_max(self):
        """ test not max. """
        self.assertEquals('results.$.test', detect_outliers.translate_field_name('test', False))


def create_test_identifier(project=None, variant=None, task=None, test=None, thread_level=None):
    return OrderedDict([('project', 'sys-perf'
                         if project is None else project), ('variant', 'linux-1-node-replSet'
                                                            if variant is None else variant),
                        ('task', 'linux-1-node-replSet' if task is None else
                         task), ('test', '15_5c_update' if test is None else
                                 test), ('thread_level', '60'
                                         if thread_level is None else thread_level)])


def create_empty(i=0):
    full_series = {'test_identifier': create_test_identifier(test=str(i)), 'orders': []}
    return MagicMock(name='result ' + str(i), full_series=full_series)


def create_one(i=0, orders=None):
    test_identifier = create_test_identifier(test=str(i))
    full_series = {'test_identifier': test_identifier, 'orders': [1] if orders is None else orders}
    return MagicMock(name='result ' + str(i), full_series=full_series, outlier_orders=[])


def create_two(i=0, orders=None, outlier_orders=None):
    test_identifier = create_test_identifier(test=str(i))
    if orders is None:
        orders = range(1, 3)
    if outlier_orders is None:
        outlier_orders = [orders[-1]]

    full_series = {'test_identifier': test_identifier, 'orders': orders}
    return MagicMock(
        name='result ' + str(i), full_series=full_series, outlier_orders=outlier_orders)


def create_three(i=0, orders=None, outlier_orders=None):
    test_identifier = create_test_identifier(test=str(i))
    if orders is None:
        orders = range(1, 4)
    if outlier_orders is None:
        outlier_orders = [orders[-1]]
    full_series = {'test_identifier': test_identifier, 'orders': orders}
    return MagicMock(
        name='result ' + str(i), full_series=full_series, outlier_orders=outlier_orders)


def create_mock_task_rejector(results=None, is_patch=False, order=None, latest=None, rejected=None):
    if results is None:
        results = []
    kwargs = dict(name='task_rejector', results=results, patch=is_patch)
    if order is not None:
        kwargs['order'] = order
    if latest is not None:
        kwargs['latest'] = latest
    if rejected is not None:
        kwargs['rejected'] = rejected
    return MagicMock(**kwargs)


class TestGetUpdates(unittest.TestCase):
    """
    Test suite for the get_updates.
    """

    def test_no_results(self):
        """ test no results. """
        mock_task_rejector = create_mock_task_rejector()
        self.assertListEqual([], detect_outliers.get_updates(mock_task_rejector))

    def test_empty_orders(self):
        """ test max. """
        results = [create_empty()]
        mock_task_rejector = create_mock_task_rejector(results=results)
        self.assertListEqual([], detect_outliers.get_updates(mock_task_rejector))

    def test_one_order_no_outliers(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier(test=str(0))
        results = [create_one()]
        mock_task_rejector = create_mock_task_rejector(results=results, order=1)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 1 update one:
        #  set index 1 outlier=True
        self.assertEqual(len(updates), 1)

        update = updates[0]
        self.assertTrue(isinstance(update, pymongo.UpdateOne))

        query = get_query_for_points(test_identifier)
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 1)

        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

    def test_one_order_outlier_not_rejected(self):
        """ test one order and it is an outlier, not rejected. """
        test_identifier = create_test_identifier()
        orders = [1]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [
            MagicMock(name='result', full_series=full_series, outlier_orders=orders, latest=False)
        ]
        mock_task_rejector = create_mock_task_rejector(results=results, order=1)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 1 update one:
        #  set index 1 outlier=True
        self.assertEqual(len(updates), 1)

        update = updates[0]
        self.assertTrue(isinstance(update, pymongo.UpdateOne))

        query = get_query_for_points(test_identifier)
        self.assertDictContainsSubset(query, update._filter)
        # self.assertDictEqual({'$in': [1]}, update._filter['order'])
        self.assertEquals(update._filter['order'], 1)

        self.assertDictEqual({'$set': {'results.$.outlier': True}}, update._doc)

    def test_one_order_outlier_rejected(self):
        """ test one order and it is an outlier, rejected. """
        test_identifier = create_test_identifier()
        orders = [1]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=orders)]
        mock_task_rejector = create_mock_task_rejector(results=results, order=1, latest=True)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 1 update one:
        #  set index 1 outlier=True
        self.assertEqual(len(updates), 1)

        update = updates[0]
        self.assertTrue(isinstance(update, pymongo.UpdateOne))

        query = get_query_for_points(test_identifier)
        self.assertDictContainsSubset(query, update._filter)
        # self.assertDictEqual({'$in': [1]}, update._filter['order'])
        self.assertEquals(update._filter['order'], 1)

        self.assertDictEqual({
            '$set': {
                'results.$.outlier': True,
                'results.$.rejected': True
            }
        }, update._doc)

    def test_two_orders_no_outliers(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = [1, 2]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=[])]
        mock_task_rejector = create_mock_task_rejector(results=results)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 1 update many:
        #  set index 1 outlier=False
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 1)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))

        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'], orders)

        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

    def test_two_orders_outlier_not_rejected(self):
        """ test one order and it is an outlier. """
        results = [create_two()]
        test_identifier = create_test_identifier(test=str(0))
        mock_task_rejector = create_mock_task_rejector(results=results, rejected=False)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 2 update ones:
        #  set index 1 outlier=False
        #  set index 1 outlier=True
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 2)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))

        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 1)

        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))

        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 2)

        self.assertDictEqual({'$set': {'results.$.outlier': True}}, update._doc)

    def test_two_orders_outlier_rejected(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = [1, 2]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=[2])]
        mock_task_rejector = create_mock_task_rejector(results=results, latest=True, order=2)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 2 update ones:
        #  set index 1 outlier=False
        #  set index 1 outlier=True, rejected=True
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 2)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))

        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 1)

        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))

        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 2)

        self.assertDictEqual({
            '$set': {
                'results.$.outlier': True,
                'results.$.rejected': True
            }
        }, update._doc)

    def test_three_orders_no_outliers(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = [1, 2, 3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=[])]
        mock_task_rejector = create_mock_task_rejector(results=results)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 1 update many:
        #  set index 1 outlier=False
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 1)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'], orders)
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

    def test_three_orders_outlier_not_rejected(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = [1, 2, 3]
        outlier_orders = [3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = create_mock_task_rejector(results=results, rejected=False)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 2 updates:
        #  update 1 set index 1 outlier=False
        #  update many set index 1 outlier=True
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 2)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'],
                             list(set(orders) - set(outlier_orders)))
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], outlier_orders[0])
        self.assertDictEqual({'$set': {'results.$.outlier': True}}, update._doc)

    def test_three_orders_multipe_outliers_not_rejected(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = [1, 2, 3]
        outlier_orders = [2, 3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = create_mock_task_rejector(results=results, rejected=False)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 2 updates:
        #  update 1 set index 1 outlier=False
        #  update many set index 1 outlier=True
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 2)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 1)
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'], outlier_orders)
        self.assertDictEqual({'$set': {'results.$.outlier': True}}, update._doc)

    def test_three_orders_multiple_outliers_rejected(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = [1, 2, 3]
        outlier_orders = [2, 3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = create_mock_task_rejector(
            results=results, rejected=False, latest=True, order=3)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 3 update ones:
        #  set index 1 outlier=False
        #  set index 1 outlier=True
        #  set index 1 outlier=True, rejected=True
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 3)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 1)
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 2)
        self.assertDictEqual({'$set': {'results.$.outlier': True}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 3)
        self.assertDictEqual({
            '$set': {
                'results.$.outlier': True,
                'results.$.rejected': True
            }
        }, update._doc)

    def test_three_orders_outlier_rejected(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = [1, 2, 3]
        outlier_orders = [3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = create_mock_task_rejector(results=results, latest=True, order=3)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 2 updates:
        #  update many set index 1 outlier=False
        #  set index 1 outlier=True, rejected=True
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 2)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'],
                             list(set(orders) - set(outlier_orders)))
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 3)
        self.assertDictEqual({
            '$set': {
                'results.$.outlier': True,
                'results.$.rejected': True
            }
        }, update._doc)

    # <----------------------

    def test_multiple_orders_no_outliers(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = range(1, 11)
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=[])]
        mock_task_rejector = create_mock_task_rejector(results=results)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 1 update many:
        #  set index 1 outlier=False
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 1)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'], orders)
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

    def test_multiple_orders_outlier_not_rejected(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = range(1, 11)
        outlier_orders = range(1, 11, 2)
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = create_mock_task_rejector(results=results, rejected=False)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 2 updates:
        #  update 1 set index 1 outlier=False
        #  update many set index 1 outlier=True
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 2)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'],
                             list(set(orders) - set(outlier_orders)))
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'], outlier_orders)
        self.assertDictEqual({'$set': {'results.$.outlier': True}}, update._doc)

    def test_multiple_orders_multipe_outliers_not_rejected(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = range(1, 11)
        outlier_orders = range(1, 11, 2)
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = create_mock_task_rejector(results=results, rejected=False)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 2 update manys:
        #  set index 1 outlier=False
        #  set index 1 outlier=True
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 2)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'],
                             list(set(orders) - set(outlier_orders)))
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'], outlier_orders)
        self.assertDictEqual({'$set': {'results.$.outlier': True}}, update._doc)

    def test_multiple_orders_multiple_outliers_rejected(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = range(1, 11)
        outlier_orders = range(1, 11, 2)
        current_order = outlier_orders[-1]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = create_mock_task_rejector(
            results=results, latest=True, order=current_order)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # 3 update ones:
        #  set index 1 outlier=False
        #  set index 1 outlier=True
        #  set index 1 outlier=True, rejected=True
        query = get_query_for_points(test_identifier)

        self.assertEqual(len(updates), 3)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'],
                             list(set(orders) - set(outlier_orders)))
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertListEqual(update._filter['order']['$in'],
                             list(set(outlier_orders) - set([current_order])))
        self.assertDictEqual({'$set': {'results.$.outlier': True}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], current_order)
        self.assertDictEqual({
            '$set': {
                'results.$.outlier': True,
                'results.$.rejected': True
            }
        }, update._doc)

    def test_multiple_results_empty(self):
        """ test one order and it is an outlier. """
        results = [create_empty(i) for i in range(10)]
        mock_task_rejector = create_mock_task_rejector(results=results)
        self.assertListEqual([], detect_outliers.get_updates(mock_task_rejector))

    def test_mixed(self):
        """ test mixed results. """
        results = [
            create_empty(0),
            create_one(1),
            create_two(2, orders=range(2, 4)),
            create_two(3, orders=range(4, 6), outlier_orders=[4]),
            create_three(4, orders=range(6, 9))
        ]

        mock_task_rejector = create_mock_task_rejector(results=results, latest=True, order=8)

        updates = detect_outliers.get_updates(mock_task_rejector)

        # < --- empty has nothing
        # < --- one
        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        test_identifier = create_test_identifier(test=str(1))
        query = get_query_for_points(test_identifier)
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 1)
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        # < --- two (last order is outlier)
        update = updates.pop(0)
        test_identifier = create_test_identifier(test=str(2))
        query = get_query_for_points(test_identifier)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 2)
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 3)
        self.assertDictEqual({'$set': {'results.$.outlier': True}}, update._doc)

        # < --- two, (first order is outlier)
        update = updates.pop(0)
        test_identifier = create_test_identifier(test=str(3))
        query = get_query_for_points(test_identifier)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 5)
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 4)
        self.assertDictEqual({'$set': {'results.$.outlier': True}}, update._doc)

        # < ---- three with reject
        update = updates.pop(0)
        test_identifier = create_test_identifier(test=str(4))
        query = get_query_for_points(test_identifier)
        self.assertTrue(isinstance(update, pymongo.UpdateMany))
        self.assertDictContainsSubset(query, update._filter)
        self.assertIn('$in', update._filter['order'])
        self.assertEquals(update._filter['order']['$in'], [6, 7])
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 8)
        self.assertDictEqual({
            '$set': {
                'results.$.outlier': True,
                'results.$.rejected': True
            }
        }, update._doc)

        self.assertEqual(len(updates), 0)

    def test_patch_three_orders_multiple_outliers_rejected(self):
        """ test one order and it is an outlier. """
        test_identifier = create_test_identifier()
        orders = [1, 2, 3]
        outlier_orders = [2, 3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = create_mock_task_rejector(
            results=results, latest=True, order=3, is_patch=True)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # patch so no updates
        self.assertListEqual([], updates)


class TestUpdateOutlierStatus(unittest.TestCase):
    """
    Test suite for the update_outlier_status.
    """

    def test_empty(self):
        mock_model = MagicMock(name='model')
        updates = []
        detect_outliers.update_outlier_status(mock_model, updates)

        mock_model.db.client.start_session.assert_not_called()

    def test_update(self):
        mock_model = MagicMock(name='model')
        updates = ['updates']
        detect_outliers.update_outlier_status(mock_model, updates)

        mock_session = mock_model.db.client.start_session
        mock_session.assert_called_once_with()
        mock_start_transaction = mock_session.return_value.__enter__.return_value.start_transaction
        mock_start_transaction.assert_called_once_with()
        mock_model.db.points.bulk_write.assert_called_once_with(updates)

    def test_exception(self):
        mock_model = MagicMock(name='model')
        updates = ['updates']

        mock_model.db.points.bulk_write.side_effect = Exception('find me')
        self.assertRaisesRegexp(Exception, 'find me', detect_outliers.update_outlier_status,
                                mock_model, updates)


class TestWriteRejects(unittest.TestCase):
    """
    Test suite for the write_rejects.
    """

    def _test_file(self, exists=True):
        filename = 'reject.json'
        with patch(ns('os.path.exists')) as mock_exists,\
            patch(ns('os.remove')) as mock_remove:
            mock_exists.return_value = exists
            detect_outliers.write_rejects([], filename)
            if exists:
                mock_remove.assert_called_once_with(filename)
            else:
                mock_remove.assert_not_called()

    def test_exists(self):
        self._test_file()

    def test_not_exists(self):
        self._test_file(exists=False)

    def _test_rejects(self, size=None):
        filename = 'reject.json'
        if size is None:
            rejects = []
        else:
            rejects = [MagicMock(name=str(i), test_identifier=i) for i in range(size)]

        output = '{output}'
        with patch(ns('os.path.exists')) as mock_exists,\
             patch(ns('open'), mock_open()) as mock_file,\
             patch(ns('json.dumps')) as mock_json:
            mock_exists.return_value = False
            mock_json.return_value = output
            detect_outliers.write_rejects(rejects, filename)

            if size is None:
                mock_file.assert_not_called()
            else:
                mock_file.assert_called_once_with(filename, 'w+')
                mock_file.return_value.write.assert_called_once_with(output)

    def test_no_rejects(self):
        self._test_rejects()

    def test_rejects(self):
        self._test_rejects(size=3)


class TestLoadStatusReport(unittest.TestCase):
    """
    Test suite for the load_status_report.
    """

    def test_exception(self):
        with patch(ns('open'), mock_open()) as mock_file:
            mock_file.side_effect = Exception('find me')
            self.assertIsNone(detect_outliers.load_status_report())

    def _test_load(self, filename=None):
        output = 'output'
        with patch(ns('open'), mock_open()) as mock_file,\
             patch(ns('json.load')) as mock_json:
            mock_json.return_value = output
            if filename is None:
                actual = detect_outliers.load_status_report()
            else:
                actual = detect_outliers.load_status_report(filename)
            self.assertEquals(output, actual)

        mock_file.assert_called_once_with('report.json' if filename is None else filename)
        mock_json.assert_called_once_with(mock_file.return_value)

    def test_load(self):
        self._test_load()

    def test_load_filename(self):
        self._test_load(filename='test.json')
