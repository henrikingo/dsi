"""
Unit tests for signal_processing/detect_changes.py.
"""

import unittest
from collections import OrderedDict
from mock import ANY, MagicMock, call, patch
from testfixtures import LogCapture

import signal_processing.detect_changes as detect_changes

SYSPERF_PERF_JSON = {
    'name': 'perf',
    'task_name': 'mixed_workloads_WT',
    'project_id': 'sys-perf',
    'task_id': 'sys_perf_wtdevelop_1_node_replSet_mixed_workloads_WT_e',
    'build_id': 'sys_perf_wtdevelop_1_node_replSet_e',
    'variant': 'wtdevelop-1-node-replSet',
    'version_id': 'sys_perf_e31a40ab59fb5c784ff8d15f07c0b811bd54a516',
    'create_time': '2018-05-09T17:37:01Z',
    'is_patch': 'false',
    'order': 12196,
    'revision': 'e31a40ab59fb5c784ff8d15f07c0b811bd54a516',
    'data': {
        'results': [{
            'end': 1525891650.3229,
            'name': 'mixed_findOne',
            'results': {
                '4': {
                    'ops_per_sec': 4090.3831991417,
                    'ops_per_sec_values': [4090.3831991417]
                },
                '64': {
                    'ops_per_sec': 16183.772555978,
                    'ops_per_sec_values': [16183.772555978]
                }
            },
            'start': 1525889262.7772,
            'workload': 'mongoshell'
        }, {
            'end': 1525891650.3229,
            'name': 'mixed_insert',
            'results': {
                '4': {
                    'ops_per_sec': 3687.4042495626,
                    'ops_per_sec_values': [3687.4042495626]
                },
                '64': {
                    'ops_per_sec': 13876.06811527,
                    'ops_per_sec_values': [13876.06811527]
                }
            },
            'start': 1525889262.7772,
            'workload': 'mongoshell'
        }, {
            'end': 1525891650.3229,
            'name': 'mixed_insert_bad',
            'results': {
                '-t': {
                    'ops_per_sec': 13876.06811527,
                    'ops_per_sec_values': [13876.06811527]
                }
            },
            'start': 1525889262.7772,
            'workload': 'mongoshell'
        }],
        'storageEngine':
            'wiredTiger'
    },
    'tag': ''
}

MICROBENCHMARKS_PERF_JSON = {
    'name': 'perf',
    'task_name': 'insert',
    'project_id': 'performance',
    'task_id': 'performance_linux_mmap_repl_insert_1',
    'build_id': 'performance_linux_mmap_repl_1',
    'variant': 'linux-mmap-repl',
    'version_id': 'performance_11a3d5ccb1216da0e84d941fd48e486f72455ba4',
    'create_time': '2018-05-09T01:10:31Z',
    'is_patch': 'false',
    'order': 12711,
    'revision': '11a3d5ccb1216da0e84d941fd48e486f72455ba4',
    'data': {
        'end':
            '2018-05-09T12:45:16.821Z',
        'errors': [],
        'results': [{
            'name': 'Insert.SingleIndex.Contested.Rnd',
            'results': {
                '1': {
                    'error_values': [0, 0, 0, 0, 0],
                    'ops_per_sec':
                        11877.04484718068,
                    'ops_per_sec_values': [
                        11846.293265329501, 11910.062444306846, 11859.832347396346,
                        11930.540796935495, 11838.49538193522
                    ]
                },
                '2': {
                    'error_values': [0, 0, 0, 0, 0],
                    'ops_per_sec':
                        23343.876415435192,
                    'ops_per_sec_values': [
                        23379.00164134018, 23217.521849551656, 23394.089152517296,
                        23283.22104716019, 23445.548386606646
                    ]
                },
                '4': {
                    'error_values': [0, 0, 0, 0, 0],
                    'ops_per_sec':
                        34931.0038833827,
                    'ops_per_sec_values': [
                        35027.48172364955, 35066.68497073847, 34387.83416157422, 35224.106807228156,
                        34948.91175372311
                    ]
                },
                '8': {
                    'error_values': [0, 0, 0, 0, 0],
                    'ops_per_sec':
                        34191.62494082317,
                    'ops_per_sec_values': [
                        34520.72459943947, 33969.494612232505, 34066.9583537965, 34068.84254392139,
                        34332.104594726
                    ]
                },
                'end': '2018-05-09T11:51:32.931Z',
                'start': '2018-05-09T11:49:50.567Z'
            }
        }],
        'start':
            '2018-05-09T11:46:25.816Z',
        'storageEngine':
            'mmapv1'
    },
    'tag': ''
}

CONFIG = {'runtime_secret': {'dsi_analysis_atlas_pw': 'password'}}

SYSPERF_POINTS = [{
    'task':
        'mixed_workloads_WT',
    'project':
        'sys-perf',
    'task_id':
        'sys_perf_wtdevelop_1_node_replSet_mixed_workloads_WT_e',
    'variant':
        'wtdevelop-1-node-replSet',
    'version_id':
        'sys_perf_e31a40ab59fb5c784ff8d15f07c0b811bd54a516',
    'order':
        12196,
    'revision':
        'e31a40ab59fb5c784ff8d15f07c0b811bd54a516',
    'start':
        1525889262.7772,
    'end':
        1525891650.3229,
    'test':
        'mixed_findOne',
    'workload':
        'mongoshell',
    'max_thread_level':
        64,
    'create_time':
        '2018-05-09T17:37:01Z',
    'max_ops_per_sec':
        16183.772555978,
    'results': [{
        'thread_level': '4',
        'ops_per_sec': 4090.3831991417,
        'ops_per_sec_values': [4090.3831991417]
    }, {
        'thread_level': '64',
        'ops_per_sec': 16183.772555978,
        'ops_per_sec_values': [16183.772555978]
    }]
}, {
    'task':
        'mixed_workloads_WT',
    'project':
        'sys-perf',
    'task_id':
        'sys_perf_wtdevelop_1_node_replSet_mixed_workloads_WT_e',
    'variant':
        'wtdevelop-1-node-replSet',
    'version_id':
        'sys_perf_e31a40ab59fb5c784ff8d15f07c0b811bd54a516',
    'order':
        12196,
    'revision':
        'e31a40ab59fb5c784ff8d15f07c0b811bd54a516',
    'start':
        1525889262.7772,
    'end':
        1525891650.3229,
    'test':
        'mixed_insert',
    'workload':
        'mongoshell',
    'max_thread_level':
        64,
    'create_time':
        '2018-05-09T17:37:01Z',
    'max_ops_per_sec':
        13876.06811527,
    'results': [{
        'thread_level': '4',
        'ops_per_sec': 3687.4042495626,
        'ops_per_sec_values': [3687.4042495626]
    }, {
        'thread_level': '64',
        'ops_per_sec': 13876.06811527,
        'ops_per_sec_values': [13876.06811527]
    }]
}]

MICROBENCHMARKS_POINTS = [{
    'task':
        'insert',
    'project':
        'performance',
    'task_id':
        'performance_linux_mmap_repl_insert_1',
    'variant':
        'linux-mmap-repl',
    'version_id':
        'performance_11a3d5ccb1216da0e84d941fd48e486f72455ba4',
    'order':
        12711,
    'revision':
        '11a3d5ccb1216da0e84d941fd48e486f72455ba4',
    'start':
        '2018-05-09T11:49:50.567Z',
    'end':
        '2018-05-09T11:51:32.931Z',
    'test':
        'Insert.SingleIndex.Contested.Rnd',
    'max_thread_level':
        4,
    'create_time':
        '2018-05-09T17:37:01Z',
    'max_ops_per_sec':
        34931.0038833827,
    'results': [
        {
            'thread_level':
                '1',
            'ops_per_sec':
                11877.04484718068,
            'ops_per_sec_values': [
                11846.293265329501, 11910.062444306846, 11859.832347396346, 11930.540796935495,
                11838.49538193522
            ]
        },
        {
            'thread_level':
                '2',
            'ops_per_sec':
                23343.876415435192,
            'ops_per_sec_values': [
                23379.00164134018, 23217.521849551656, 23394.089152517296, 23283.22104716019,
                23445.548386606646
            ]
        },
        {
            'thread_level':
                '4',
            'ops_per_sec':
                34931.0038833827,
            'ops_per_sec_values': [
                35027.48172364955, 35066.68497073847, 34387.83416157422, 35224.106807228156,
                34948.91175372311
            ]
        },
        {
            'thread_level':
                '8',
            'ops_per_sec':
                34191.62494082317,
            'ops_per_sec_values': [
                34520.72459943947, 33969.494612232505, 34066.9583537965, 34068.84254392139,
                34332.104594726
            ]
        },
    ]
}]

MONGO_URI = 'mongodb+srv://fake@dummy-server.mongodb.net'
DATABASE = 'perf'


class TestDetectChanges(unittest.TestCase):
    """
    Test suite for non-class functions in detect_changes.py.
    """

    # pylint: disable=invalid-name
    @patch('signal_processing.detect_changes.MongoClient', autospec=True)
    def test__upload_json(self, mock_MongoClient):
        """
        Test that _upload_config_json works with a standard configuration.
        """
        mock_db = MagicMock(name='db', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        detect_changes._upload_json(SYSPERF_PERF_JSON, MONGO_URI, DATABASE)
        mock_MongoClient.assert_called_once_with(MONGO_URI)
        mock_MongoClient.return_value.get_database.assert_called_once_with(DATABASE)
        mock_db.points.insert.assert_called_once_with(SYSPERF_POINTS)

    # pylint: enable=invalid-name

    def test__get_thread_levels(self):
        for i, result in enumerate(SYSPERF_PERF_JSON['data']['results']):
            if i < len(SYSPERF_POINTS):
                actual = detect_changes._get_thread_levels(result)
                self.assertEqual(actual, SYSPERF_POINTS[i]['results'])
        for i, result in enumerate(MICROBENCHMARKS_PERF_JSON['data']['results']):
            actual = detect_changes._get_thread_levels(result)
            self.assertEqual(actual, MICROBENCHMARKS_POINTS[i]['results'])

    def test__get_max_ops_per_sec(self):
        bad_point = {'max_thread_level': None, 'max_ops_per_sec': None}
        for i, result in enumerate(SYSPERF_PERF_JSON['data']['results']):
            point = SYSPERF_POINTS[i] if i < len(SYSPERF_POINTS) else bad_point
            with LogCapture() as log:
                actual = detect_changes._get_max_ops_per_sec(result)
                if point is bad_point:
                    log.check(('signal_processing.detect_changes', 'WARNING',
                               'Invalid thread level value -t found'))
                else:
                    log.check()
            self.assertEqual(actual, (point['max_thread_level'], point['max_ops_per_sec']))
        for i, result in enumerate(MICROBENCHMARKS_PERF_JSON['data']['results']):
            point = MICROBENCHMARKS_POINTS[i]
            actual = detect_changes._get_max_ops_per_sec(result)
            self.assertEqual(actual, (point['max_thread_level'], point['max_ops_per_sec']))

    def test__extract_tests(self):
        """
        Test that _extract_tests works with a correctly formatted perf.json file.
        """
        tests = set(['mixed_insert', 'mixed_findOne', 'mixed_insert_bad'])
        self.assertEqual(detect_changes._extract_tests(SYSPERF_PERF_JSON), tests)


class TestDetectChangesDriver(unittest.TestCase):
    """
    Test suite for the DetectChangesDriver class.
    """

    # pylint: disable=invalid-name
    @patch('signal_processing.detect_changes.PointsModel', autospec=True)
    def test_run(self, mock_PointsModel):
        tests = set(['mixed_insert', 'mixed_findOne'])
        mock__print_result = MagicMock(name='_print_result', autospec=True)
        mock_table = mock_PointsModel.return_value
        mock_table.compute_change_points.return_value = ('dummy1', 'dummy2', 'dummy3')
        detect_changes.DetectChangesDriver._print_result = mock__print_result
        test_driver = detect_changes.DetectChangesDriver(SYSPERF_PERF_JSON, MONGO_URI, DATABASE)
        test_driver.run()
        mock_PointsModel.assert_called_once_with(SYSPERF_PERF_JSON, MONGO_URI, DATABASE)
        compute_change_points_calls = [call(test) for test in tests]
        mock_table.compute_change_points.assert_has_calls(
            compute_change_points_calls, any_order=True)
        print_result_calls = [call('dummy1', 'dummy2', 'dummy3', test) for test in tests]
        mock__print_result.assert_has_calls(print_result_calls, any_order=True)

    # pylint: enable=invalid-name


class TestPointsModel(unittest.TestCase):
    """
    Test suite for the PointsModel class.
    """

    # pylint: disable=invalid-name
    @patch('signal_processing.detect_changes.MongoClient', autospec=True)
    def test_init(self, mock_MongoClient):
        """
        Test that proper database connection.
        """
        detect_changes.PointsModel(SYSPERF_PERF_JSON, MONGO_URI, DATABASE)
        mock_MongoClient.assert_called_once_with(MONGO_URI)
        mock_MongoClient.return_value.get_database.assert_called_once_with(DATABASE)

    @patch('signal_processing.detect_changes.MongoClient', autospec=True)
    def test_get_points(self, mock_MongoClient):
        expected_query = OrderedDict(
            [('project', SYSPERF_PERF_JSON['project_id']),
             ('variant', SYSPERF_PERF_JSON['variant']), ('task', SYSPERF_PERF_JSON['task_name']),
             ('test', SYSPERF_PERF_JSON['data']['results'][0]['name'])])
        expected_projection = {
            'max_ops_per_sec': 1,
            'revision': 1,
            'order': 1,
            'create_time': 1,
            '_id': 0
        }
        expected_series = [point['max_ops_per_sec'] for point in SYSPERF_POINTS]
        expected_revisions = [point['revision'] for point in SYSPERF_POINTS]
        expected_orders = [point['order'] for point in SYSPERF_POINTS]
        expected_create_times = [point['create_time'] for point in SYSPERF_POINTS]
        expected_num_points = len(SYSPERF_POINTS)
        mock_db = MagicMock(name='db', autospec=True)
        mock_cursor = MagicMock(name='cursor', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        mock_db.points.find.return_value.sort = mock_cursor
        mock_cursor.return_value = SYSPERF_POINTS
        test_table = detect_changes.PointsModel(SYSPERF_PERF_JSON, MONGO_URI, DATABASE)
        actual = test_table.get_points(SYSPERF_PERF_JSON['data']['results'][0]['name'])
        self.assertEqual(actual, (expected_series, expected_revisions, expected_orders,
                                  expected_query, expected_create_times, expected_num_points))
        mock_db.points.find.assert_called_once_with(expected_query, expected_projection)
        mock_db.points.find.return_value.sort.assert_called_once_with([('order', 1)])

    @patch('signal_processing.detect_changes.MongoClient', autospec=True)
    def test_get_points_custom_limit(self, mock_MongoClient):
        """
        Test that limit is called on cursor when specified.
        """
        limit = 10
        mock_db = MagicMock(name='db', autospec=True)
        mock_cursor = MagicMock(name='cursor', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        mock_db.points.find.return_value.sort = mock_cursor
        test_table = detect_changes.PointsModel(SYSPERF_PERF_JSON, MONGO_URI, DATABASE, limit=limit)
        test_table.get_points(SYSPERF_PERF_JSON['data']['results'][0]['name'])
        mock_cursor.return_value.limit.assert_called_with(limit)

    @patch('signal_processing.detect_changes.MongoClient', autospec=True)
    def test_compute_change_points(self, mock_MongoClient):
        expected_query = OrderedDict(
            [('project', SYSPERF_PERF_JSON['project_id']),
             ('variant', SYSPERF_PERF_JSON['variant']), ('task', SYSPERF_PERF_JSON['task_name']),
             ('test', SYSPERF_PERF_JSON['data']['results'][0]['name'])])
        mock_db = MagicMock(name='db', autospec=True)
        mock_bulk = MagicMock(name='bulk', autospec=True)
        mock_get_points = MagicMock(name='get_points', autospec=True)
        mock_QHat = MagicMock(name='QHat', autospec=True)
        mock_MongoClient.return_value.get_database.return_value = mock_db
        mock_db.change_points.initialize_ordered_bulk_op.return_value = mock_bulk
        mock_get_points.return_value = ['series', 'revisions', 'query', 'many_points']
        detect_changes.QHat = mock_QHat
        test = SYSPERF_PERF_JSON['data']['results'][0]['name']
        test_table = detect_changes.PointsModel(SYSPERF_PERF_JSON, MONGO_URI, DATABASE)
        actual = test_table.compute_change_points(test)
        mock_QHat.assert_called_once_with(
            {
                'series': [],
                'revisions': [],
                'orders': [],
                'create_times': [],
                'testname': test
            },
            pvalue=None)
        mock_db.change_points.initialize_ordered_bulk_op.assert_called_once()
        mock_bulk.find.assert_called_once_with(expected_query)
        mock_bulk.find.return_value.remove.assert_called_once()
        mock_bulk.execute.assert_called_once()
        self.assertEqual(actual, (0, 0, ANY))

    # pylint: enable=invalid-name
