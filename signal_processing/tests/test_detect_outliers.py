"""
Unit tests for signal_processing/detect_outliers.py.
"""
# pylint: disable=too-many-lines

import os
import re
import unittest

import pymongo
from mock import MagicMock, call, patch, ANY, mock_open

import signal_processing.detect_outliers as detect_outliers
from signal_processing.commands.helpers import get_query_for_points
from signal_processing.detect_outliers import DETECTED_TYPE, SUSPICIOUS_TYPE
from signal_processing.detect_outliers import main, _translate_outliers
from signal_processing.model.configuration import DEFAULT_CONFIG, OutlierConfiguration, \
    DEFAULT_MAX_CONSECUTIVE_REJECTIONS, DEFAULT_MINIMUM_POINTS, DEFAULT_CANARY_PATTERN, \
    DEFAULT_CORRECTNESS_PATTERN
from signal_processing.tests.helpers import Helpers
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
        override_config = DEFAULT_CONFIG
        test_driver = detect_outliers.DetectOutliersDriver(self.sysperf_perf_json, override_config,
                                                           MONGO_URI, is_patch)
        self.assertEquals(test_driver.pool_size, 200)

    def test_constructor_pool_size(self):
        """ test pool size. """
        is_patch = False
        override_config = DEFAULT_CONFIG
        test_driver = detect_outliers.DetectOutliersDriver(
            self.sysperf_perf_json, override_config, MONGO_URI, is_patch, pool_size=99)
        self.assertEquals(test_driver.pool_size, 99)

    # pylint: disable=too-many-locals
    def test_run(self):
        """ test run. """

        with patch(ns('multiprocessing.cpu_count'), autospec=True) as mock_cpu_count, \
             patch(ns('jobs.Job'), autospec=True) as mock_job_cls,\
             patch(ns('jobs.process_jobs'), autospec=True) as mock_process_jobs,\
             patch(ns('PointsModel'), autospec=True) as mock_PointsModel,\
             patch(ns('ConfigurationModel'), autospec=True) as mock_ConfigurationModel:

            mock_job = MagicMock(name='mock_job')
            mock_job_cls.return_value = mock_job

            mock_process_jobs.return_value = ()
            mock_cpu_count.return_value = 101
            mock_points_model = mock_PointsModel.return_value
            mock_configuration_model = mock_ConfigurationModel.return_value

            test_identifiers = [{
                'project': self.sysperf_perf_json['project_id'],
                'variant': self.sysperf_perf_json['variant'],
                'task': self.sysperf_perf_json['task_name'],
                'test': test,
                'thread_level': '1'
            } for test in (u'mixed_insert', u'mixed_insert_bad', u'mixed_findOne')]

            mock_points_model.db.points.aggregate.return_value = test_identifiers
            is_patch = False
            override_config = {}
            test_driver = detect_outliers.DetectOutliersDriver(self.sysperf_perf_json,
                                                               override_config, MONGO_URI, is_patch)
            test_driver.run()
            mock_PointsModel.assert_called_once_with(MONGO_URI)
            mock_ConfigurationModel.assert_called_once_with(MONGO_URI)

            calls = [
                call(
                    detect_outliers._get_data_and_run_detection,
                    arguments=(mock_points_model, mock_configuration_model, test_identifier,
                               self.sysperf_perf_json['order'], override_config, is_patch),
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
        override_config = DEFAULT_CONFIG
        with patch(ns('evergreen_client.Client'), autospec=True),\
             patch(ns('helpers.extract_test_identifiers')) as mock_extract_test_identifiers:

            mock_extract_test_identifiers.return_value = []
            completed_jobs = detect_outliers.detect_outliers(
                task_id, override_config, MONGO_URI, is_patch, pool_size, rejects_file, progressbar)
            self.assertListEqual([], completed_jobs)

    def _test(self, mock_driver, mock_evg_cl, successful_jobs=None, whitelisted=None):
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
            if whitelisted is not None:
                mock_task_rejector_clazz.return_value = MagicMock(
                    name='task_rejector', whitelisted=whitelisted)

            mock_extract_test_identifiers.return_value = [{
                'project': project,
                'variant': variant,
                'task': task
            }]
            override_config = DEFAULT_CONFIG
            mock_load.return_value = status
            detect_outliers.detect_outliers(task_id, override_config, MONGO_URI, is_patch,
                                            pool_size, rejects_file, progressbar)

        mock_load.assert_called_once()
        mock_driver.assert_called_once_with(
            mock_perf_json,
            override_config,
            MONGO_URI,
            is_patch,
            pool_size=pool_size,
            progressbar=progressbar)
        mock_runner.run.assert_called_once()
        if mock_runner.run.return_value:
            mock_task_rejector = mock_task_rejector_clazz.return_value
            if whitelisted:
                rejects = []
            else:
                rejects = mock_task_rejector_clazz.return_value.filtered_rejects.return_value

            mock_task_rejector_clazz.assert_called_once_with(['result'], project, variant, task,
                                                             mock_perf_json, MONGO_URI, is_patch,
                                                             status, override_config)
            mock_get_updates.assert_called_once_with(mock_task_rejector)
            mock_update_outlier_status.assert_called_once_with(mock_task_rejector.points_model,
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
        self._test(mock_driver, mock_evg_cl, successful_jobs, whitelisted=False)

    @patch(ns('evergreen_client.Client'), autospec=True)
    @patch(ns('DetectOutliersDriver'), autospec=True)
    def test_reject_whitelisted(self, mock_driver, mock_evg_cl):
        """
        Test detect_outliers.detect_outliers rejection functionality.
        """
        successful_jobs = [MagicMock(name='success', exception=False, result='result')]
        self._test(mock_driver, mock_evg_cl, successful_jobs, whitelisted=True)


class TestRunDetection(unittest.TestCase):
    # pylint: disable=protected-access, too-many-locals
    """
    Test suite for the detect_outliers function. These tests do not depend on each other and can
    run in any order.
    """

    FILE_PARTS = [
        'sys-perf', 'linux-1-node-replSet', 'bestbuy_query', 'canary_client-cpuloop-10x', '1'
    ]

    def load(self, fixture_name, *file_path):
        """
        load the test data associated with test_name.

        :param str fixture_name: The name of the test data to load.
        :param str file_path: The parts of the path to load the data from. An empty list implies
        use FILE_PARTS.
        :return: A tuple of expected data and test data.
        """
        if not file_path:
            file_path = self.FILE_PARTS
        file_parts = list(file_path) + ['{}.json'.format(fixture_name)]

        filename = os.path.join(*file_parts)
        fixture = FIXTURE_FILES.load_json_file(filename)
        expected = fixture['expected']
        data = fixture['data']
        return expected, data

    def _test(self, expected, data):
        """
        Test detect_outliers.detect_outliers function with real data and configuration.
        """

        is_patch = False
        with patch(ns('Outlier'), autospec=True) as mock_outlier_ctor,\
             patch(ns('pymongo.InsertOne'), autospec=True) as insert_mock,\
             patch(ns('pymongo.DeleteMany'), autospec=True) as delete_mock,\
             patch(ns('get_change_point_range'), autospec=True) as get_change_point_range_mock,\
             patch(ns('combine_outlier_configs'), autospec=True) as combine_outlier_configs_mock:

            expected_number_outliers = expected['number_outliers']

            points_model_mock = MagicMock(name='points_model')
            configuration_model_mock = MagicMock(name='configuration_mdodel')
            time_series = data['time_series']
            test_identifier = {
                'project': time_series['project'],
                'variant': time_series['variant'],
                'task': time_series['task'],
                'test': time_series['test'],
                'thread_level': time_series['thread_level'],
            }

            start_order = data.get('start_order', None)
            end_order = data.get('end_order', None)

            orders = time_series['orders']
            if start_order is None and end_order is None:
                start = 0
                start_order = time_series['orders'][0]
                end = None
                series = time_series['series']
            elif end_order is None:
                start = orders.index(start_order)
                end = None

                series = time_series['series'][start:]
            elif start_order is None:
                start = 0
                start_order = time_series['orders'][0]

                end = orders.index(end_order)
                series = time_series['series'][:end]
            else:
                start = orders.index(start_order)
                end = orders.index(end_order)
                series = time_series['series'][start:end]

            expected_suspicious_indexes = expected['suspicious_indexes']

            get_change_point_range_mock.return_value = (start, end, series)

            expected_range = list(range(len(expected_suspicious_indexes)))

            points_model_mock.get_points.return_value = time_series
            mock_outlier_ctor.return_value._asdict.side_effect = expected_range
            deletes = ['delete']
            if expected_number_outliers:
                inserts = ['insert {}'.format(i) for i in expected_range]
            else:
                inserts = []

            requests = deletes + inserts

            delete_mock.side_effect = deletes
            insert_mock.side_effect = inserts

            mock_client = points_model_mock.db.client
            mock_session = mock_client.start_session.return_value.__enter__.return_value
            mock_outliers_collection = points_model_mock.db.__getitem__.return_value

            mock_config = MagicMock(name='configuration')
            override_config = mock_config

            configuration = OutlierConfiguration(
                max_outliers=OUTLIERS_PERCENTAGE / 100.0,
                mad=MAD,
                significance_level=SIGNIFICANCE_LEVEL,
                max_consecutive_rejections=DEFAULT_MAX_CONSECUTIVE_REJECTIONS,
                minimum_points=DEFAULT_MINIMUM_POINTS,
                canary_pattern=DEFAULT_CANARY_PATTERN,
                correctness_pattern=DEFAULT_CORRECTNESS_PATTERN)

            combine_outlier_configs_mock.return_value = configuration

            outlier_results = detect_outliers._get_data_and_run_detection(
                points_model_mock, configuration_model_mock, test_identifier, start_order,
                override_config, is_patch)

            mock_outliers_collection.bulk_write.assert_called_once_with(requests, ordered=True)
            mock_client.start_session.assert_called_once()
            mock_session.start_transaction.return_value.__enter__.assert_called_once()

            gesd_result = outlier_results.gesd_result
            self.assertEquals(gesd_result.count, expected_number_outliers)
            self.assertListEqual(gesd_result.suspicious_indexes, expected_suspicious_indexes)

            expected = dict(test_identifier, order={'$gte': start_order})
            if end_order is not None:
                expected['order']['$lt'] = end_order

            delete_mock.assert_called_once_with(expected)

            insert_mock.assert_has_calls([call(i) for i in range(len(inserts))])

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
                    num_outliers=ANY,
                    configuration=configuration._asdict())
                for pos, _ in enumerate(expected_suspicious_indexes[:expected_number_outliers])
            ])

    def test_standard(self):
        """
        Test detect_outliers.detect_outliers with standard data.
        """
        expected, data = self.load('standard')
        self._test(expected, data)

    def test_before_change_points(self):
        """
        Test detect_outliers with order before the first change point.
        """
        expected, data = self.load('start_to_first_change_point')
        self._test(expected, data)

    def test_between_change_points(self):
        """
        Test detect_outliers with order between the first and second change points.
        """
        expected, data = self.load('first_to_second_change_point')
        self._test(expected, data)

    def test_after_change_points(self):
        """
        Test detect_outliers with order after the last change points.
        """
        expected, data = self.load('last_change_point_to_end')
        self._test(expected, data)

    def test_tig1665(self):
        """
        Test detect_outliers.detect_outliers with data that specifically failed in TIG-1665. The
        unpatched code left a 'leaked' outlier on each run.
        """
        expected, data = self.load('standard', 'sys-perf', 'linux-1-node-replSet', 'linkbench',
                                   'LOAD_COUNTS_BULK', '1')
        self._test(expected, data)


class TestTranslateOutliers(unittest.TestCase):
    """
    Test suite for the _save_outliers function
    """

    def test_no_gesd_results(self):
        """ test when no gesd results. """
        gesd_result = None
        test_identifier = {}
        start = 0
        num_outliers = 1
        full_series = []
        configuration = DEFAULT_CONFIG
        outliers = _translate_outliers(gesd_result, test_identifier, start, num_outliers,
                                       full_series, configuration)
        self.assertEqual(0, len(outliers))

    def test_gesd_count_of_zero_no_indexes(self):
        """ test when gesd count == 0 and no indexes. """
        gesd_result = MagicMock(count=0, suspicious_indexes=[])
        test_identifier = {}
        start = 0
        num_outliers = 1
        full_series = []
        configuration = DEFAULT_CONFIG
        outliers = _translate_outliers(gesd_result, test_identifier, start, num_outliers,
                                       full_series, configuration)
        self.assertEqual(0, len(outliers))

    def test_gesd_count_of_zero_with_indexes(self):
        """ test when gesd count == 0 and indexes. """
        gesd_result = MagicMock(
            count=0,
            suspicious_indexes=[0],
            critical_values=['critical value 0'],
            test_statistics=['test statistic 0'],
        )
        test_identifier = Helpers.create_test_identifier()
        start = 0
        num_outliers = 1
        start_order = 100
        full_series = {
            'orders': [start_order],
            'revisions': ['revision 1'],
            'create_times': ['create time 1'],
            'task_ids': ['task id 1'],
            'version_ids': ['version id 1'],
        }
        configuration = DEFAULT_CONFIG
        with patch(ns('Outlier'), autospec=True):
            outliers = _translate_outliers(gesd_result, test_identifier, start, num_outliers,
                                           full_series, configuration)
        self.assertEqual(0, len(outliers))

    def test_gesd(self):
        """ test when gesd count > 0. """
        gesd_result = MagicMock(
            count=1,
            suspicious_indexes=[0],
            critical_values=['critical value 0'],
            test_statistics=['test statistic 0'],
        )
        test_identifier = Helpers.create_test_identifier()
        start = 0
        num_outliers = 1
        start_order = 100
        full_series = {
            'orders': [start_order],
            'revisions': ['revision 1'],
            'create_times': ['create time 1'],
            'task_ids': ['task id 1'],
            'version_ids': ['version id 1'],
        }
        configuration = DEFAULT_CONFIG
        with patch(ns('Outlier'), autospec=True) as mock_outlier_ctor:
            outliers = _translate_outliers(gesd_result, test_identifier, start, num_outliers,
                                           full_series, configuration)
        self.assertEqual(1, len(outliers))
        mock_outlier_ctor.assert_called_once_with(
            type=DETECTED_TYPE,
            project=test_identifier['project'],
            variant=test_identifier['variant'],
            task=test_identifier['task'],
            test=test_identifier['test'],
            thread_level=test_identifier['thread_level'],
            revision='revision 1',
            task_id='task id 1',
            version_id='version id 1',
            order=100,
            create_time='create time 1',
            change_point_revision='revision 1',
            change_point_order=100,
            order_of_outlier=0,
            z_score='test statistic 0',
            critical_value='critical value 0',
            num_outliers=1,
            configuration=configuration._asdict())

    def test_gesd_multiple(self):
        """ test when gesd count > 1. """
        gesd_result = MagicMock(
            count=1,
            suspicious_indexes=[0, 1],
            critical_values=['critical value 0', 'critical value 2'],
            test_statistics=['test statistic 0', 'test statistic 2'],
        )
        test_identifier = Helpers.create_test_identifier()
        start = 0
        num_outliers = 1
        start_order = 100
        full_series = {
            'orders': [start_order, start_order + 2],
            'revisions': ['revision 0', 'revision 2'],
            'create_times': ['create time 0', 'create time 2'],
            'task_ids': ['task id 0', 'task id 2'],
            'version_ids': ['version id 0', 'version id 2'],
        }
        configuration = DEFAULT_CONFIG
        with patch(ns('Outlier'), autospec=True) as mock_outlier_ctor:
            outliers = _translate_outliers(gesd_result, test_identifier, start, num_outliers,
                                           full_series, configuration)
        self.assertEqual(2, len(outliers))
        common = dict(
            project=test_identifier['project'],
            variant=test_identifier['variant'],
            task=test_identifier['task'],
            test=test_identifier['test'],
            thread_level=test_identifier['thread_level'],
            change_point_revision='revision 0',
            change_point_order=100,
            num_outliers=1,
            configuration=configuration._asdict())

        first = common.copy()
        first.update(
            type=DETECTED_TYPE,
            revision='revision 0',
            task_id='task id 0',
            version_id='version id 0',
            order=100,
            create_time='create time 0',
            order_of_outlier=0,
            z_score='test statistic 0',
            critical_value='critical value 0')
        second = common.copy()
        second.update(
            type=SUSPICIOUS_TYPE,
            revision='revision 2',
            task_id='task id 2',
            version_id='version id 2',
            order=102,
            create_time='create time 2',
            order_of_outlier=1,
            z_score='test statistic 2',
            critical_value='critical value 2')

        expected_calls = [call(**first), call(**second)]
        mock_outlier_ctor.assert_has_calls(expected_calls, any_order=True)


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
    @patch(ns('OutlierConfiguration'), autospec=True)
    def test_is_patch(self, mock_outlier_config, mock_logging, mock_config_dict,
                      mock_detect_outliers):
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

        mock_outlier_config.assert_called_once_with(
            max_outliers=None,
            mad=None,
            significance_level=None,
            max_consecutive_rejections=None,
            minimum_points=None)
        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(False, filename='detect_outliers.log')

        rejects_file = 'rejects.json'
        pool_size = None

        mock_detect_outliers.assert_called_once_with(
            'tid',
            mock_outlier_config.return_value,
            'muri',
            is_patch,
            pool_size,
            rejects_file,
            progressbar=False)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    @patch(ns('OutlierConfiguration'), autospec=True)
    def test_defaults(self, mock_outlier_config, mock_logging, mock_config_dict,
                      mock_detect_outliers):
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

        mock_outlier_config.assert_called_once_with(
            max_outliers=None,
            mad=None,
            significance_level=None,
            max_consecutive_rejections=None,
            minimum_points=None)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(False, filename='detect_outliers.log')

        rejects_file = 'rejects.json'
        pool_size = None

        mock_detect_outliers.assert_called_once_with(
            'tid',
            mock_outlier_config.return_value,
            'muri',
            is_patch,
            pool_size,
            rejects_file,
            progressbar=False)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    @patch(ns('OutlierConfiguration'), autospec=True)
    def test_params(self, mock_outlier_config, mock_logging, mock_config_dict,
                    mock_detect_outliers):
        """
        Test main with params.
        """
        is_patch = False
        mock_detect_outliers.return_value = []
        mock_config = mock_config_dict.return_value
        mock_config.__getitem__.side_effect = self.config.__getitem__

        pool_size = 1
        max_outliers = 0.4
        significance = 0.2
        rejections = 10
        min_points = 100

        result = self.runner.invoke(main, [
            '-l', 'logfile', '--pool-size',
            str(pool_size), '--max-outliers',
            str(max_outliers), '--mad', '--significance',
            str(significance), '--progressbar', '-v', '--rejections',
            str(rejections), '--minimum',
            str(min_points)
        ])
        self.assertEqual(result.exit_code, 0)

        mock_outlier_config.assert_called_once_with(
            max_outliers=max_outliers,
            mad=True,
            significance_level=significance,
            max_consecutive_rejections=rejections,
            minimum_points=min_points)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(True, filename='logfile')

        rejects_file = 'rejects.json'

        mock_detect_outliers.assert_called_once_with(
            'tid',
            mock_outlier_config.return_value,
            'muri',
            is_patch,
            pool_size,
            rejects_file,
            progressbar=True)

    @patch(ns('detect_outliers'), autospec=True)
    @patch(ns('config.ConfigDict'), autospec=True)
    @patch(ns('log.setup_logging'), autospec=True)
    @patch(ns('OutlierConfiguration'), autospec=True)
    def test_outliers_0(self, mock_outlier_config, mock_logging, mock_config_dict,
                        mock_detect_outliers):
        """
        Test main with params.
        """
        is_patch = False
        mock_detect_outliers.return_value = []
        mock_config = mock_config_dict.return_value
        mock_config.__getitem__.side_effect = self.config.__getitem__

        rejects_file = 'watch.json'
        pool_size = 1
        max_outliers = 0
        significance = 0.2
        rejections = 5
        min_points = 10

        result = self.runner.invoke(main, [
            '-l', 'logfile', '--pool-size',
            str(pool_size), '--max-outliers',
            str(max_outliers), '--mad', '--significance',
            str(significance), '--rejects-file', rejects_file, '--rejections',
            str(rejections), '--minimum',
            str(min_points), '--progressbar', '-v'
        ])
        self.assertEqual(result.exit_code, 0)

        mock_outlier_config.assert_called_once_with(
            max_outliers=max_outliers,
            mad=True,
            significance_level=significance,
            max_consecutive_rejections=rejections,
            minimum_points=min_points)

        mock_config_dict.assert_called_once()
        mock_config.load.assert_called_once()
        mock_logging.assert_called_once_with(True, filename='logfile')

        mock_detect_outliers.assert_called_once_with(
            'tid',
            mock_outlier_config.return_value,
            'muri',
            is_patch,
            pool_size,
            rejects_file,
            progressbar=True)

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
        if end is None:
            expected = self.full_series['series'][start:]
        else:
            expected = self.full_series['series'][start:end]
        self.assertListEqual(expected, series)

    def test_after_last_range(self):
        """ test after last range. """
        self._test(102, 90, None)

    def test_in_last_range(self):
        """ test last range. """
        self._test(93, 90, None)

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
        self.assertEqual(None, end)
        self.assertListEqual(self.full_series['series'], series)


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


def create_empty(i=0, reject=False):
    """
    create mock empty test rejector result.
    :param i: result id,
    :param bool reject: The reject status,
    :return: A mock empty test rejector result
    """
    full_series = {'test_identifier': Helpers.create_test_identifier(test=str(i)), 'orders': []}
    result = MagicMock(name='result ' + str(i), full_series=full_series)
    result.reject.return_value = reject
    return result


def create_one(i=0, orders=None, reject=False):
    """
    create single mock test rejector result.
    :param i: result id,
    :param orders: The orders,
    :param bool reject: The reject status,
    :return: A single mock test rejector result
    """
    test_identifier = Helpers.create_test_identifier(test=str(i))
    full_series = {'test_identifier': test_identifier, 'orders': [1] if orders is None else orders}
    result = MagicMock(name='result ' + str(i), full_series=full_series, outlier_orders=[])
    result.reject.return_value = reject
    return result


def create_two(i=0, orders=None, outlier_orders=None, reject=False):
    """
    create 2 mock test rejector result.
    :param i: result id,
    :param orders: The orders,
    :param outlier_orders: The outlier orders,
    :param bool reject: The reject status,
    :return: A list of mock test rejector result
    """
    test_identifier = Helpers.create_test_identifier(test=str(i))
    if orders is None:
        orders = range(1, 3)
    if outlier_orders is None:
        outlier_orders = [orders[-1]]

    full_series = {'test_identifier': test_identifier, 'orders': orders}
    result = MagicMock(
        name='result ' + str(i), full_series=full_series, outlier_orders=outlier_orders)
    result.reject.return_value = reject
    return result


def create_three(i=0, orders=None, outlier_orders=None, reject=False):
    """
    create 3 mock test rejector result.
    :param i: result id,
    :param orders: The orders,
    :param outlier_orders: The outlier orders,
    :param bool reject: The reject status,
    :return: A list of mock test rejector result
    """
    test_identifier = Helpers.create_test_identifier(test=str(i))
    if orders is None:
        orders = range(1, 4)
    if outlier_orders is None:
        outlier_orders = [orders[-1]]
    full_series = {'test_identifier': test_identifier, 'orders': orders}
    result = MagicMock(
        name='result ' + str(i), full_series=full_series, outlier_orders=outlier_orders)
    result.reject.return_value = reject
    return result


class TestGetUpdates(unittest.TestCase):
    """
    Test suite for the get_updates.
    """

    def test_no_results(self):
        """ test no results. """
        mock_task_rejector = Helpers.create_mock_task_rejector()
        self.assertListEqual([], detect_outliers.get_updates(mock_task_rejector))

    def test_empty_orders(self):
        """ test max. """
        results = [create_empty()]
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results)
        self.assertListEqual([], detect_outliers.get_updates(mock_task_rejector))

    def test_one_order_no_outliers(self):
        """ test one order and it is an outlier. """
        test_identifier = Helpers.create_test_identifier(test=str(0))
        results = [create_one()]
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results, order=1)
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
        test_identifier = Helpers.create_test_identifier()
        orders = [1]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        result = MagicMock(
            name='result', full_series=full_series, outlier_orders=orders, latest=False)
        result.reject.return_value = False
        results = [result]
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results, order=1)
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
        test_identifier = Helpers.create_test_identifier()
        orders = [1]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=orders)]
        mock_task_rejector = Helpers.create_mock_task_rejector(
            results=results, order=1, latest=True)
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
        test_identifier = Helpers.create_test_identifier()
        orders = [1, 2]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        result = MagicMock(name='result', full_series=full_series, outlier_orders=[])
        result.reject.return_value = False
        results = [result]
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results)
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
        test_identifier = Helpers.create_test_identifier(test=str(0))
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results, rejected=False)
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
        test_identifier = Helpers.create_test_identifier()
        orders = [1, 2]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=[2])]
        mock_task_rejector = Helpers.create_mock_task_rejector(
            results=results, latest=True, order=2)
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
        test_identifier = Helpers.create_test_identifier()
        orders = [1, 2, 3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        result = MagicMock(name='result', full_series=full_series, outlier_orders=[])
        result.reject.return_value = False
        results = [result]
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results)
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
        test_identifier = Helpers.create_test_identifier()
        orders = [1, 2, 3]
        outlier_orders = [3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        result = MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)
        result.reject.return_value = False
        results = [result]
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results, rejected=False)
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
        test_identifier = Helpers.create_test_identifier()
        orders = [1, 2, 3]
        outlier_orders = [2, 3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        result = MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)
        result.reject.return_value = False
        results = [result]
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results, rejected=False)
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
        test_identifier = Helpers.create_test_identifier()
        orders = [1, 2, 3]
        outlier_orders = [2, 3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = Helpers.create_mock_task_rejector(
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
        test_identifier = Helpers.create_test_identifier()
        orders = [1, 2, 3]
        outlier_orders = [3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = Helpers.create_mock_task_rejector(
            results=results, latest=True, order=3)
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
        test_identifier = Helpers.create_test_identifier()
        orders = range(1, 11)
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        result = MagicMock(name='result', full_series=full_series, outlier_orders=[])
        result.reject.return_value = False
        results = [result]
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results)
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
        test_identifier = Helpers.create_test_identifier()
        orders = range(1, 11)
        outlier_orders = range(1, 11, 2)
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        result = MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)
        result.reject.return_value = False
        results = [result]
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results, rejected=False)
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
        test_identifier = Helpers.create_test_identifier()
        orders = range(1, 11)
        outlier_orders = range(1, 11, 2)
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        result = MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)
        result.reject.return_value = False
        results = [result]
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results, rejected=False)
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
        test_identifier = Helpers.create_test_identifier()
        orders = range(1, 11)
        outlier_orders = range(1, 11, 2)
        current_order = outlier_orders[-1]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = Helpers.create_mock_task_rejector(
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
        mock_task_rejector = Helpers.create_mock_task_rejector(results=results)
        self.assertListEqual([], detect_outliers.get_updates(mock_task_rejector))

    def test_mixed(self):
        """ test mixed results. """
        results = [
            create_empty(0),
            create_one(1),
            create_two(2, orders=range(2, 4)),
            create_two(3, orders=range(4, 6), outlier_orders=[4]),
            create_three(4, orders=range(6, 9), outlier_orders=[8], reject=True)
        ]

        mock_task_rejector = Helpers.create_mock_task_rejector(
            results=results, latest=True, order=8)

        updates = detect_outliers.get_updates(mock_task_rejector)

        # < --- empty has nothing
        # < --- one
        update = updates.pop(0)
        self.assertTrue(isinstance(update, pymongo.UpdateOne))
        test_identifier = Helpers.create_test_identifier(test=str(1))
        query = get_query_for_points(test_identifier)
        self.assertDictContainsSubset(query, update._filter)
        self.assertEquals(update._filter['order'], 1)
        self.assertDictEqual({'$set': {'results.$.outlier': False}}, update._doc)

        # < --- two (last order is outlier)
        update = updates.pop(0)
        test_identifier = Helpers.create_test_identifier(test=str(2))
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
        test_identifier = Helpers.create_test_identifier(test=str(3))
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
        test_identifier = Helpers.create_test_identifier(test=str(4))
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
        test_identifier = Helpers.create_test_identifier()
        orders = [1, 2, 3]
        outlier_orders = [2, 3]
        full_series = {'test_identifier': test_identifier, 'orders': orders}
        results = [MagicMock(name='result', full_series=full_series, outlier_orders=outlier_orders)]
        mock_task_rejector = Helpers.create_mock_task_rejector(
            results=results, latest=True, order=3, is_patch=True)
        updates = detect_outliers.get_updates(mock_task_rejector)

        # patch so no updates
        self.assertListEqual([], updates)


# pylint: disable=no-self-use
class TestUpdateOutlierStatus(unittest.TestCase):
    """
    Test suite for the update_outlier_status.
    """

    def test_empty(self):
        """ test empty updates. """
        mock_model = MagicMock(name='model')
        updates = []
        detect_outliers.update_outlier_status(mock_model, updates)

        mock_model.db.client.start_session.assert_not_called()

    def test_update(self):
        """ test with updates. """
        mock_model = MagicMock(name='model')
        updates = ['updates']
        detect_outliers.update_outlier_status(mock_model, updates)

        mock_session = mock_model.db.client.start_session
        mock_session.assert_called_once_with()
        mock_start_transaction = mock_session.return_value.__enter__.return_value.start_transaction
        mock_start_transaction.assert_called_once_with()
        mock_model.db.points.bulk_write.assert_called_once_with(updates)

    def test_exception(self):
        """ test raises exception. """
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
        """ test write rejects file exists. """
        self._test_file()

    def test_not_exists(self):
        """ test write rejects file does not exists. """
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
        """ test no rejects. """
        self._test_rejects()

    def test_rejects(self):
        """ test rejects. """
        self._test_rejects(size=3)


class TestLoadStatusReport(unittest.TestCase):
    """
    Test suite for the load_status_report.
    """

    def test_exception(self):
        """ test with exception. """
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
        """ test load default filename. """
        self._test_load()

    def test_load_filename(self):
        """ test load non-default filename. """
        self._test_load(filename='test.json')


class TestFullSeries(unittest.TestCase):
    # pylint: disable=protected-access, too-many-locals
    """
    Test Full Series is more of a system test. These tests do not depend on each other and can
    run in any order.

    They use the real state of the sys-perf linux-1-node-replSet linkbench canary_ping 16 tests
    at the current point in time (May 2019).

    It covers the following possibilities:
        1) The revision is before the first change point (first). This simulates the rerunning of
        a very old revision and rerunning a moderately old revision when there is only a single
        change point.
        2) The revision is between 2 change points (second). These simulate running an
        old revision.
        3) The revision is after the last change points but not the latest revision(fourth).
        3) The revision is after the last change points and is the latest revision (latest). This
        simulates the most common case of running the latest revision.

    This suite of tests ensures that real data with multiple
    change points generates the correct bounds (start / end) and outliers.

    """

    FILE_PARTS = [
        'sys-perf', 'linux-1-node-replSet', 'linkbench', 'canary_ping', '16', 'full_series'
    ]

    def load(self, fixture_name):
        """
        load the test data associated with fixture_name.

        :param str fixture_name: The name of the test data to load.
        :return: A tuple of test data (contains the input params and expected data) and the full
        fixture data.
        """
        filename = os.path.join(*self.FILE_PARTS) + '.json'
        fixture = FIXTURE_FILES.load_json_file(filename)

        test = next(test for test in fixture['tests'] if test['name'] == fixture_name)
        return test, fixture

    def _test(self, test, fixture):
        """
        test helper function.

        :param dict test: The test data, including the input params and expected results.
        :param dict fixture: The full fixture data.
        """

        expected = test['expected']
        is_patch = False
        canary_pattern = re.compile('^(canary_.*|fio_.*|iperf.*|NetworkBandwidth)$'),
        correctness_pattern = re.compile(
            '^(db-hash-check|validate-indexes-and-collections|core\\.).*$')
        with patch(ns('_save_outliers'), autospec=True) as _save_outliers_mock,\
             patch(ns('combine_outlier_configs'), autospec=True) as combine_outlier_configs_mock:

            points_model_mock = MagicMock(name='points_model')
            configuration_model_mock = MagicMock(name='configuration_mdodel')
            full_series = fixture['data']['full_series']
            test_identifier = {
                'project': full_series['project'],
                'variant': full_series['variant'],
                'task': full_series['task'],
                'test': full_series['test'],
                'thread_level': full_series['thread_level'],
            }

            points_model_mock.get_points.return_value = full_series
            change_points_col_mock = MagicMock(name='change_points collection')

            change_points_col_mock.find.return_value.sort.return_value = fixture['data'][
                'change_points']

            collections = {'change_points': change_points_col_mock}
            points_model_mock.db.get_collection.side_effect = lambda name: collections[name]

            mock_config = MagicMock(name='configuration')
            override_config = mock_config

            configuration = OutlierConfiguration(
                max_outliers=0.15,
                mad=False,
                significance_level=0.05,
                max_consecutive_rejections=3,
                minimum_points=15,
                canary_pattern=canary_pattern,
                correctness_pattern=correctness_pattern)

            combine_outlier_configs_mock.return_value = configuration

            order = test['order']

            outlier_results = detect_outliers._get_data_and_run_detection(
                points_model_mock, configuration_model_mock, test_identifier, order,
                override_config, is_patch)

            gesd_result = outlier_results.gesd_result

            expected_start = expected.get('start', 0)
            self.assertEquals(outlier_results.start, expected_start)

            expected_end = expected.get('end', None)
            self.assertEquals(outlier_results.end, expected_end)

            expected_count = expected['count']
            self.assertEquals(gesd_result.count, expected_count)

            expected_suspicious_indexes = expected['suspicious_indexes']
            self.assertEquals(gesd_result.suspicious_indexes, expected_suspicious_indexes)

    def test_before_change_points(self):
        """ Test from with order that is before first change point. """
        test, fixture = self.load("Before first change point")
        self._test(test, fixture)

    def test_between_change_points(self):
        """ Test from first to second change point. """
        test, fixture = self.load("Between first and second change points")
        self._test(test, fixture)

    def test_after_last_change_point(self):
        """ Test from last change point to end. """
        test, fixture = self.load("After last change point")
        self._test(test, fixture)

    def test_current_revision(self):
        """ Test where order is lateset revision and after last change point. """
        test, fixture = self.load("Order is current revision")
        self._test(test, fixture)
