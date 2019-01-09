"""
Unit tests for signal_processing/helpers.py.
"""
import re
import time
import unittest
from collections import OrderedDict

import click
import mock
from mock import patch

import signal_processing.commands.helpers as helpers
import signal_processing.commands.jobs as jobs
from signal_processing.keyring.credentials import Credentials


class TestIsMaxThreadLevel(unittest.TestCase):
    """
    Test suite for is_max_thread_level.
    """

    def _test_is_max_thread_level(self, test_identifier, expected):
        """
        Test generate_thread_levels identifier.
        """
        self.assertEquals(helpers.is_max_thread_level(test_identifier), expected)

    def test_empty(self):
        """
        Test no thread_level set.
        """
        self._test_is_max_thread_level({}, False)

    def test_max(self):
        """
        Test max thread_level set.
        """
        self._test_is_max_thread_level({'thread_level': 'max'}, True)

    def test_not_max(self):
        """
        Test thread_level set but not max.
        """
        self._test_is_max_thread_level({'thread_level': '1'}, False)


class TestGenerateThreadLevels(unittest.TestCase):
    """
    Test suite for generate_thread_levels.
    """

    def _test_generate_thread_levels(self, return_value=(), expected=None):
        """
        Test generate_thread_levels identifier.
        """
        return_value = list(return_value)
        mock_collection = mock.MagicMock(name="points collection")
        mock_collection.aggregate.return_value = return_value
        actual = list(helpers.generate_thread_levels('test_identifier', mock_collection))
        if expected is None:
            expected = return_value
        self.assertEquals(actual, expected)

        calls = mock_collection.aggregate.call_args_list
        self.assertEquals(len(calls), 1)
        arguments = calls[0][0][0]

        self.assertEquals(arguments[0], {'$match': 'test_identifier'})

    def test_identifier(self):
        """
        Test generate_thread_levels identifier.
        """
        self._test_generate_thread_levels()

    def test_yields(self):
        """
        Test generate_thread_levels yields.
        """
        self._test_generate_thread_levels(return_value=[{'thread_level': '1'}])

    def test_yields_max(self):
        """
        Test generate_thread_levels yields.
        """
        return_value = [{'thread_level': '1'}, {'thread_level': '2'}]
        self._test_generate_thread_levels(
            return_value=return_value, expected=return_value + [{
                'thread_level': 'max'
            }])


class TestGetQueryForPoints(unittest.TestCase):
    """
    Test suite for the get_query_for_points.
    """

    def _test(self, test_identifier, expected=None):
        """ test helper. """
        if expected is None:
            expected = test_identifier

        self.assertEquals(expected, helpers.get_query_for_points(test_identifier))

    def test_empty(self):
        """ test empty. """
        self._test({})

    def test_not_empty(self):
        """ test not empty. """

        self._test({
            'project': 'project_id',
            'variant': 'variant',
            'task': 'task_name',
            'test': 'testname'
        })

    def test_thread_level(self):
        """ test a thread level. """

        self._test({'thread_level': '1'}, {'results.thread_level': '1'})

    def test_max_thread_level(self):
        """ test a thread level. """

        self._test({'thread_level': 'max'}, {})


class TestReadConfig(unittest.TestCase):
    """
    Test suite for the read_default_config.
    """

    def _test_app_conf_location(self, app_conf_location=None, count=2):
        """
        Test helper for env var support.

        :parameter app_conf_location: The additional application directory.
        :type app_conf_location: str or None.
        :parameter int count: The expected count.
        """
        with patch('signal_processing.commands.helpers.click') as mock_click, \
             patch('signal_processing.commands.helpers.os.path') as mock_path, \
             patch('signal_processing.commands.helpers.open') as mock_open:

            mock_path.exists.return_value = False
            mock_path.isfile.return_value = False
            mock_path.isdir.return_value = False
            mock_click.get_app_dir.return_value = '/tmp/app_name'
            self.assertEquals({}, helpers.read_default_config('app_name', app_conf_location))
            mock_click.get_app_dir.assert_called_once_with(
                'app_name', roaming=True, force_posix=True)
            mock_open.assert_not_called()
            self.assertEqual(mock_path.exists.call_count, count)

    def test_no_env(self):
        """ Test no env var passed in."""
        self._test_app_conf_location()

    def test_env(self):
        """ Test env var passed in."""
        self._test_app_conf_location('app_dir', 3)

    @patch('signal_processing.commands.helpers.click', autospec=True)
    @patch('signal_processing.commands.helpers.os.path', autospec=True)
    @patch('signal_processing.commands.helpers.open')
    @patch('signal_processing.commands.helpers.yaml.load')
    def test_first_file(self, mock_yaml, mock_open, mock_path, mock_click):
        """ Test first file is loaded."""

        expected = {'config': 'contents'}
        mock_yaml.return_value = expected
        mock_path.exists.return_value = True
        mock_path.isfile.return_value = True
        mock_path.isdir.return_value = True
        mock_path.join.return_value = 'joined name'

        mock_click.get_app_dir.return_value = '/tmp/app_name'
        self.assertEquals(expected, helpers.read_default_config('app_name', 'app_dir'))
        mock_click.get_app_dir.assert_called_once_with('app_name', roaming=True, force_posix=True)
        mock_open.assert_called_once_with('joined name')

    @patch('signal_processing.commands.helpers.click', autospec=True)
    @patch('signal_processing.commands.helpers.os.path', autospec=True)
    @patch('signal_processing.commands.helpers.open')
    @patch('signal_processing.commands.helpers.yaml.load')
    def test_second_file(self, mock_yaml, mock_open, mock_path, mock_click):
        """ Test instance attributes."""

        expected = {'config': 'contents'}
        mock_yaml.return_value = expected
        mock_path.exists.return_value = True
        mock_path.isfile.side_effect = [False, True, True]
        mock_path.join.side_effect = ['second', 'third']
        mock_path.isdir.return_value = True

        mock_click.get_app_dir.return_value = '/tmp/app_name'
        self.assertEquals(expected, helpers.read_default_config('app_name', 'app_dir'))
        mock_click.get_app_dir.assert_called_once_with('app_name', roaming=True, force_posix=True)
        mock_open.assert_called_once_with('second')

    @patch('signal_processing.commands.helpers.click', autospec=True)
    @patch('signal_processing.commands.helpers.os.path', autospec=True)
    @patch('signal_processing.commands.helpers.open')
    @patch('signal_processing.commands.helpers.yaml.load')
    def test_third_file(self, mock_yaml, mock_open, mock_path, mock_click):
        """ Test third file."""

        expected = {'config': 'contents'}
        mock_yaml.return_value = expected
        mock_path.exists.return_value = True
        mock_path.isfile.side_effect = [False, False, True]
        mock_path.join.side_effect = ['second', 'third']
        mock_path.isdir.return_value = True

        mock_click.get_app_dir.return_value = '/tmp/app_name'
        self.assertEquals(expected, helpers.read_default_config('app_name', 'app_dir'))
        mock_click.get_app_dir.assert_called_once_with('app_name', roaming=True, force_posix=True)
        mock_open.assert_called_once_with('third')


# pylint: disable=invalid-name
class TestCommandConfiguration(unittest.TestCase):
    """
    Test suite for the CommandConfiguration class.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'

    @patch('signal_processing.commands.helpers.new_mongo_client', autospec=True)
    @patch('signal_processing.commands.helpers.parse_uri', autospec=True)
    @patch('signal_processing.commands.helpers.get_git_credentials', autospec=True)
    def test_attributes(self, mock_get_git_credentials, mock_parse_uri, mock_mongo_client):
        """ Test instance attributes."""
        mongo_client_instance = mock_mongo_client.return_value
        mock_database = mongo_client_instance.get_database.return_value
        mock_collection = mock_database.get_collection.return_value

        mock_parse_uri.return_value = {'database': 'database name'}
        mock_get_git_credentials.return_value = 'credentials'

        subject = helpers.CommandConfiguration(
            debug='debug',
            log_file='/tmp/log_file',
            out='out',
            file_format='file_format',
            mongo_uri='mongo_uri',
            queryable='queryable',
            dry_run='dry_run',
            compact='compact',
            style=('style', ),
            token_file='token_file',
            mongo_repo='mongo_repo')

        self.assertEqual('debug', subject.debug)
        self.assertEqual('out', subject.out)
        self.assertEqual('file_format', subject.file_format)
        self.assertEqual('queryable', subject.queryable)
        self.assertEqual('dry_run', subject.dry_run)
        self.assertEqual('compact', subject.compact)

        self.assertEqual('database name', subject.database_name)

        self.assertEqual('points', subject.points_name)
        self.assertEqual('change_points', subject.change_points_name)
        self.assertEqual('processed_change_points', subject.processed_change_points_name)
        self.assertEqual('unprocessed_change_points', subject.unprocessed_change_points_name)
        self.assertEqual('build_failures', subject.build_failures_name)
        self.assertEqual(('style', ), subject.style)
        self.assertEqual('token_file', subject.token_file)
        self.assertEqual('credentials', subject.credentials)
        self.assertEqual('mongo_repo', subject.mongo_repo)

        self.assertEqual(mock_database, subject.database)
        self.assertEqual(mock_collection, subject.points)
        self.assertEqual(mock_collection, subject.change_points)
        self.assertEqual(mock_collection, subject.processed_change_points)
        self.assertEqual(mock_collection, subject.unprocessed_change_points)
        self.assertEqual(mock_collection, subject.build_failures)

    @patch('signal_processing.commands.helpers.new_mongo_client', autospec=True)
    def test_mongo_username_password_can_be_specified(self, new_mongo_client_mock):
        subject = helpers.CommandConfiguration(
            debug='debug',
            log_file='/tmp/log_file',
            out='out',
            file_format='file_format',
            mongo_uri='mongodb://mongo_uri',
            queryable='queryable',
            dry_run='dry_run',
            compact='compact',
            style=('style', ),
            token_file='token_file',
            mongo_repo='mongo_repo',
            mongo_username='mongo_user',
            mongo_password='mongo_password')

        self.assertEquals(new_mongo_client_mock.return_value, subject.mongo_client)

        new_mongo_client_mock.assert_called_with(
            'mongodb://mongo_uri',
            auth_type=None,
            credentials=Credentials('mongo_user', 'mongo_password'))

    @patch('signal_processing.commands.helpers.new_mongo_client', autospec=True)
    def test_mongo_keyring_can_be_specified(self, new_mongo_client_mock):
        subject = helpers.CommandConfiguration(
            debug='debug',
            log_file='/tmp/log_file',
            out='out',
            file_format='file_format',
            mongo_uri='mongodb://mongo_uri',
            queryable='queryable',
            dry_run='dry_run',
            compact='compact',
            style=('style', ),
            token_file='token_file',
            mongo_repo='mongo_repo',
            auth_mode='keyring')

        self.assertEquals(new_mongo_client_mock.return_value, subject.mongo_client)

        new_mongo_client_mock.assert_called_with(
            'mongodb://mongo_uri', auth_type='keyring', credentials=None)


class TestFlagsToValue(unittest.TestCase):
    """
    Test flags_to_value.
    """

    def test_flags_to_value_blank(self):
        """ Test blank flag."""
        self.assertEqual(helpers.flags_to_value(''), 0)

    def test_flags_to_value_mi(self):
        """ Test mi flags."""
        self.assertEqual(helpers.flags_to_value('mi'), 10)


class TestExtractPattern(unittest.TestCase):
    """
    Test extract_to_pattern.
    """

    # comparing compiled re's seem to be randomly broken
    # on linux falling back to asserting that the compile is
    # called.
    def test_extract_pattern_empty(self):
        """ Test empty."""
        self.assertEqual(helpers.extract_pattern(''), '')
        self.assertEqual(helpers.extract_pattern(None), None)

    def test_extract_pattern_string(self):
        """ Test string."""
        self.assertEqual(helpers.extract_pattern('string'), 'string')

    def test_extract_pattern_string_is_not_pattern(self):
        """ Test string but not pattern."""
        self.assertEqual(helpers.extract_pattern('string', string_is_pattern=False), 'string')

    @patch('signal_processing.commands.helpers.re.compile', autospec=True, return_value='pattern')
    def test_extract_pattern_string_is_pattern(self, mock_compile):
        """ Test string pattern."""
        self.assertEqual(helpers.extract_pattern('string', string_is_pattern=True), 'pattern')
        mock_compile.assert_called_once_with('string', 0)

    @patch('signal_processing.commands.helpers.re.compile', autospec=True, return_value='pattern')
    def test_extract_pattern_string_pattern(self, mock_compile):
        """ Test string pattern."""
        self.assertEqual(helpers.extract_pattern('/string/mi'), 'pattern')
        mock_compile.assert_called_once_with('string', re.M + re.I)


class TestProcessParams(unittest.TestCase):
    """
    Test process_params.
    """

    # comparing compiled re's seem to be randomly broken
    # on linux falling back to asserting that the compile is
    # called.
    def test_process_params_empty(self):
        """ Test empty."""
        self.assertEqual(helpers.process_params('', '', '', '', revision='', thread_level=''), {})
        self.assertEqual(helpers.process_params(None, None, None, None), {})

    def test_process_params_strings(self):
        """ Test strings."""
        expected = {
            k: k
            for k in ('suspect_revision', 'project', 'variant', 'task', 'test', 'thread_level')
        }
        actual = helpers.process_params(
            'project',
            'variant',
            'task',
            'test',
            revision='suspect_revision',
            thread_level='thread_level')
        self.assertDictEqual(expected, actual)

    @patch(
        'signal_processing.commands.helpers.re.compile',
        autospec=True,
        side_effect=[1, 2, 3, 4, 5, 6])
    def test_process_params_re_strings(self, mock_compile):
        """ Test re strings."""
        expected = {
            'suspect_revision': 1,
            'project': 2,
            'variant': 3,
            'task': 4,
            'test': 5,
            'thread_level': 6
        }
        actual = helpers.process_params(
            '/project/',
            '/variant/',
            '/task/',
            '/test/',
            revision='/suspect_revision/',
            thread_level='/thread_level/')
        self.assertDictEqual(expected, actual)
        calls = [
            mock.call('suspect_revision', 0),
            mock.call('project', 0),
            mock.call('variant', 0),
            mock.call('task', 0),
            mock.call('test', 0),
            mock.call('thread_level', 0),
        ]
        mock_compile.assert_has_calls(calls=calls)


class TestProcessParamsForPoints(unittest.TestCase):
    """
    Test process_params.
    """

    # comparing compiled re's seem to be randomly broken
    # on linux falling back to asserting that the compile is
    # called.
    def test_process_params_empty(self):
        """ Test empty."""
        self.assertEqual(
            helpers.process_params_for_points('', '', '', '', revision='', thread_level=''), {})
        self.assertEqual(helpers.process_params_for_points(None, None, None, None), {})

    def test_process_params_strings(self):
        """ Test strings."""
        expected = {
            k: k
            for k in ('revision', 'project', 'variant', 'task', 'test', 'thread_level')
        }
        actual = helpers.process_params_for_points(
            'project', 'variant', 'task', 'test', revision='revision', thread_level='thread_level')
        self.assertDictEqual(expected, actual)

    @patch(
        'signal_processing.commands.helpers.re.compile',
        autospec=True,
        side_effect=[1, 2, 3, 4, 5, 6])
    def test_process_params_re_strings(self, mock_compile):
        """ Test re strings."""
        expected = {
            'revision': 1,
            'project': 2,
            'variant': 3,
            'task': 4,
            'test': 5,
            'thread_level': 6
        }
        actual = helpers.process_params_for_points(
            '/project/',
            '/variant/',
            '/task/',
            '/test/',
            revision='/revision/',
            thread_level='/thread_level/')
        self.assertDictEqual(expected, actual)
        calls = [
            mock.call('revision', 0),
            mock.call('project', 0),
            mock.call('variant', 0),
            mock.call('task', 0),
            mock.call('test', 0),
            mock.call('thread_level', 0),
        ]
        mock_compile.assert_has_calls(calls=calls)


class TestProcessExcludes(unittest.TestCase):
    """
    Test process_excludes.
    """

    # comparing compiled re's seem to be randomly broken
    # on linux falling back to asserting that the compile is
    # called.
    def test_process_excludes_empty(self):
        """ Test empty."""
        self.assertEqual(helpers.process_excludes([]), [])

    @patch('signal_processing.commands.helpers.re.compile', autospec=True, side_effect=[1])
    def test_process_excludes_string(self, mock_compile):
        """ Test string."""
        self.assertEqual(helpers.process_excludes(['string']), [1])
        mock_compile.assert_called_once_with('string', 0)

    @patch('signal_processing.commands.helpers.re.compile', autospec=True, side_effect=[1, 2])
    def test_process_excludes_pattern(self, mock_compile):
        """ Test pattern."""
        self.assertEquals([1, 2], helpers.process_excludes(['string1', 'string2']))

        calls = [mock.call('string1', 0), mock.call('string2', 0)]
        mock_compile.assert_has_calls(calls=calls)


class TestOrder(unittest.TestCase):
    """
    Test order function.
    """

    def test_order_empty(self):
        """ Test empty."""
        self.assertEqual(helpers.order({}), {})

    def test_order_reversed(self):
        """ Test reversed order."""
        reversed_dict = OrderedDict([(key, key) for key in reversed(helpers.DEFAULT_KEY_ORDER)])

        self.assertEqual(
            helpers.order(reversed_dict),
            OrderedDict([(key, key) for key in helpers.DEFAULT_KEY_ORDER]))

    def test_order_reversed_single(self):
        """ Test single reversed."""
        values = [(key, key) for key in ['b', 'a'] + ['_id']]

        reversed_dict = OrderedDict(values)

        self.assertEqual(
            helpers.order(reversed_dict), OrderedDict([('_id', '_id'), ('a', 'a'), ('b', 'b')]))


class TestStringifyJson(unittest.TestCase):
    """
    Test stringify_json.
    """

    def test_stringify_json_empty(self):
        """ Test empty."""
        self.assertEqual(helpers.stringify_json({}), '{}')

    def test_stringify_json_default(self):
        """ Test with defaults."""
        expected = """{
    "a": "a"
}"""
        self.assertEqual(helpers.stringify_json({'a': 'a'}), expected)

    def test_stringify_json_compact(self):
        """ Test compact."""
        expected = """{"a": "a"}"""
        self.assertEqual(helpers.stringify_json({'a': 'a'}, compact=True), expected)

    def test_stringify_json_keys(self):
        """ Test keys and compact."""
        expected = """{"_id": "id", "a": "a"}"""
        self.assertEqual(helpers.stringify_json({'a': 'a', '_id': 'id'}, compact=True), expected)

    def test_stringify_json_with_keys(self):
        """ Test compact order with keys."""
        expected = '{"a": "a", "_id": "id"}'
        self.assertEqual(
            helpers.stringify_json({
                'a': 'a',
                '_id': 'id'
            }, compact=True, keys=['a']), expected)


class TestFilterExcludes(unittest.TestCase):
    """
    Test filter_excludes.
    """

    def setUp(self):
        self.expected = {'first': 'first'}

    def test_filter_excludes_empty(self):
        """ Test empty."""
        self.assertEqual(list(helpers.filter_excludes([], [], [])), [])

    def test_filter_excludes_empty_keys(self):
        """ Test empty keys."""
        self.assertEqual(
            list(helpers.filter_excludes([self.expected], [], [])), [{
                'first': 'first'
            }])

    def test_filter_excludes_empty_patterns(self):
        """ Test empty patterns."""
        self.assertEqual(
            list(helpers.filter_excludes([self.expected], ['first'], [])), [{
                'first': 'first'
            }])

    def test_filter_excludes(self):
        """ Test excludes."""
        self.assertEqual(
            list(
                helpers.filter_excludes([{
                    'first': 'first',
                    'second': 'second'
                }], ['second'], [re.compile('second')])), [])

    def test_filter_2_excludes(self):
        """ Test 2 excludes."""
        self.assertEqual(
            list(
                helpers.filter_excludes([self.expected, {
                    'second': 'second'
                }], ['second'], [re.compile('second')])), [{
                    'first': 'first'
                }])


class TestItemShowFunc(unittest.TestCase):
    """
    Test show_item_function.
    """

    def test_empty(self):
        """ Test empty."""
        self.assertEqual(helpers.show_item_function(None), None)

    def test_string(self):
        """ Test string."""
        self.assertEqual(helpers.show_item_function(''), None)

    def test_dict(self):
        """ Test dict."""
        item = {
            'project': 'project',
            'variant': 'variant',
            'task': 'task',
            'thread_level': 'thread_level'
        }
        expected = 'thread_level/task/variant/project'
        actual = helpers.show_item_function(item)
        self.assertEqual(expected, actual)

    def test_short(self):
        """ Test short."""
        item = {
            'project': 'project',
            'variant': 'variant',
            'task': 'task',
            'thread_level': 'thread_level'
        }
        expected = 'thread_level/task/variant'
        actual = helpers.show_item_function(item, info_width=42)
        self.assertEqual(expected, actual)

    def test_shorter(self):
        """ Test shorter."""
        item = {
            'project': 'project',
            'variant': 'variant',
            'task': 'task',
            'thread_level': 'thread_level'
        }
        expected = 'thread_level/task'
        actual = helpers.show_item_function(item, info_width=32)
        self.assertEqual(expected, actual)

    def test_shortest(self):
        """ Test shorter."""
        item = {
            'project': 'project',
            'variant': 'variant',
            'task': 'task',
            'thread_level': 'thread_level'
        }
        expected = 'thread_level'
        actual = helpers.show_item_function(item, info_width=22)
        self.assertEqual(expected, actual)

    def test_job(self):
        """ Test shorter."""
        expected = 'task'
        item = jobs.Job(time.sleep, identifier=expected)
        self.assertEqual(expected, helpers.show_item_function(item, info_width=16))


class TestGetMatchingTasks(unittest.TestCase):
    """
    Test get_matching_tasks.
    """

    def _test(self, no_older=True, revision=False):
        """ Test the core function."""
        self.assertEqual(helpers.show_item_function(None), None)
        database = mock.MagicMock(name='database')

        database.aggregate.return_value = 'expected'
        if revision:
            query = {'revision': 'badf'}
        else:
            query = {'find': 'me'}

        value = helpers.get_matching_tasks(database, query, 30 if no_older else None)
        self.assertEqual(value, 'expected')
        database.aggregate.assert_called_once()
        arguments = database.aggregate.call_args_list[0][0][0]
        match = arguments[0]['$match']
        self.assertDictContainsSubset(query, match)

        if no_older:
            self.assertIn('start', match)

        if revision:
            arguments = database.aggregate.call_args_list[0][0][0]
            grouping = arguments[1]['$group']
            self.assertIn('_id', grouping)
            self.assertIn('revision', grouping['_id'])
            self.assertEquals('$revision', grouping['_id']['revision'])

            projection = arguments[-1]['$project']
            self.assertIn('revision', projection)
            self.assertEquals('$_id.revision', projection['revision'])

    def test_get_matching_tasks(self):
        """ Test the core function."""
        self._test()

    def test_get_matching_tasks_no_older(self):
        """ Test the core function with no older."""
        self._test(no_older=True)

    def test_get_matching_tasks_revision(self):
        """ Test the core function with revision."""
        self._test(revision=True)


class TestGetMatchingChangePoints(unittest.TestCase):
    """
    Test get_matching_change_points.
    """

    def test_get_matching_change_points(self):
        """ Test the core function."""
        self.assertEqual(helpers.show_item_function(None), None)
        database = mock.MagicMock(name='database')

        database.aggregate.return_value = 'expected'
        test_identifier = {'find': 'me'}

        value = helpers.get_matching_tasks(database, test_identifier)
        self.assertEqual(value, 'expected')
        database.aggregate.assert_called_once()
        arguments = database.aggregate.call_args_list[0][0][0]
        match = arguments[0]['$match']
        self.assertEquals(test_identifier, match)


class TestFilterTests(unittest.TestCase):
    """
    Test filter_tests.
    """

    def test_filter_tests_empty(self):
        """ Test empty."""
        expected = False
        actual = helpers.filter_tests('', [re.compile('first')])
        self.assertEqual(expected, actual)

    def test_filter_tests_empty_patterns(self):
        """ Test empty pattern."""
        expected = False
        actual = helpers.filter_tests('', [])
        self.assertEqual(expected, actual)

    def test_filter_tests_True(self):
        """ Test matching."""
        expected = True
        actual = helpers.filter_tests('first', [re.compile('first')])
        self.assertEqual(expected, actual)

    def test_filter_tests_False(self):
        """ Test not matching."""
        expected = False
        actual = helpers.filter_tests('second', [re.compile('first')])
        self.assertEqual(expected, actual)

    def test_filter_tests_multiple_true(self):
        """ Test multiple matches."""
        expected = True
        actual = helpers.filter_tests('second', [re.compile('first'), re.compile('second')])
        self.assertEqual(expected, actual)

    def test_filter_tests_multiple_false(self):
        """ Test multiple mismatch."""
        expected = False
        actual = helpers.filter_tests('second', [re.compile('first'), re.compile('third')])
        self.assertEqual(expected, actual)


class TestGenerateTests(unittest.TestCase):
    """
    Test generate_tests.
    """

    def test_generate_tests_empty(self):
        """ Test empty."""
        expected = []
        actual = list(helpers.generate_tests([]))
        self.assertEqual(expected, actual)

    def test_generate_tests_one(self):
        """ Test one."""
        expected = [{'test': 'first'}]
        actual = list(helpers.generate_tests([{'tests': ['first']}]))
        self.assertEqual(expected, actual)

    def test_generate_tests_two(self):
        """ Test two."""
        expected = [{'test': 'first'}, {'test': 'second'}]
        actual = list(helpers.generate_tests([{'tests': ['first', 'second']}]))
        self.assertEqual(expected, actual)

    def test_generate_tests_combined(self):
        """ Test combined."""
        expected = [{'test': 'first', 'first': 'task'}, {'test': 'second', 'second': 'task'}]
        actual = list(
            helpers.generate_tests([{
                'tests': ['first'],
                'first': 'task'
            }, {
                'tests': ['second'],
                'second': 'task'
            }]))
        self.assertEqual(expected, actual)


class TestValidate(unittest.TestCase):
    """
    Test validate_int_none_options.
    """

    def test_invalid_string(self):
        """ Test not int."""
        self.assertRaisesRegexp(click.BadParameter, 'twelve is not a valid integer or None.',
                                helpers.validate_int_none_options, None, None, 'twelve')

    def test_invalid_number(self):
        """ Test invalid number."""
        self.assertRaisesRegexp(click.BadParameter, '1.2 is not a valid integer or None.',
                                helpers.validate_int_none_options, None, None, '1.2')

    def test_valid_numbers(self):
        """ Test valid numbers."""
        self.assertEquals(-1, helpers.validate_int_none_options(None, None, '-1'))
        self.assertEquals(0, helpers.validate_int_none_options(None, None, '0'))
        self.assertEquals(1, helpers.validate_int_none_options(None, None, '1'))

    def test_valid_value(self):
        """ Test None."""
        self.assertIsNone(helpers.validate_int_none_options(None, None, 'None'))
        self.assertIsNone(helpers.validate_int_none_options(None, None, 'none'))

    def test_int_value(self):
        """ Test int value."""
        self.assertEquals(1, helpers.validate_int_none_options(None, None, 1))
