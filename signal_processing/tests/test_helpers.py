"""
Unit tests for signal_processing/helpers.py.
"""
import re
import unittest
from collections import OrderedDict

import mock
from mock import patch

import signal_processing.commands.helpers as helpers


# pylint: disable=invalid-name
class TestCommandConfiguration(unittest.TestCase):
    """
    Test suite for the CommandConfiguration class.
    """

    def setUp(self):
        self.mongo_uri = 'mongodb+srv://fake@dummy-server.mongodb.net/perf'

    @patch('signal_processing.commands.helpers.MongoClient', autospec=True)
    @patch('signal_processing.commands.helpers.parse_uri', autospec=True)
    def test_attributes(self, mock_parse_uri, mock_mongo_client):
        """ Test instance attributes."""
        mongo_client_instance = mock_mongo_client.return_value
        mock_database = mongo_client_instance.get_database.return_value
        mock_collection = mock_database.get_collection.return_value

        mock_parse_uri.return_value = {'database': 'database name'}

        subject = helpers.CommandConfiguration(
            'debug', 'out', 'file_format', self.mongo_uri, 'queryable', 'dry_run', 'compact',
            'points', 'change_points', 'processed_change_points', 'build_failures', ('style', ),
            'credentials', 'mongo_repo')

        self.assertEqual('debug', subject.debug)
        self.assertEqual('out', subject.out)
        self.assertEqual('file_format', subject.format)
        self.assertEqual('queryable', subject.queryable)
        self.assertEqual('dry_run', subject.dry_run)
        self.assertEqual('compact', subject.compact)

        self.assertEqual('database name', subject.database_name)

        self.assertEqual('points', subject.points_name)
        self.assertEqual('change_points', subject.change_points_name)
        self.assertEqual('processed_change_points', subject.processed_change_points_name)
        self.assertEqual('build_failures', subject.build_failures_name)
        self.assertEqual(('style', ), subject.style)
        self.assertEqual('credentials', subject.credentials)
        self.assertEqual('mongo_repo', subject.mongo_repo)

        self.assertEqual(mock_database, subject.database)
        self.assertEqual(mock_collection, subject.points)
        self.assertEqual(mock_collection, subject.change_points)
        self.assertEqual(mock_collection, subject.processed_change_points)
        self.assertEqual(mock_collection, subject.build_failures)


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

    def setUp(self):
        self.pattern = re.compile('string', re.M | re.I)

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

    def test_extract_pattern_string_is_pattern(self):
        """ Test string pattern."""
        self.assertEqual(
            helpers.extract_pattern('string', string_is_pattern=True), re.compile('string'))

    def test_extract_pattern_string_pattern(self):
        """ Test string pattern."""
        self.assertEqual(helpers.extract_pattern('/string/mi'), self.pattern)


class TestProcessParams(unittest.TestCase):
    """
    Test process_params.
    """

    def test_process_params_empty(self):
        """ Test empty."""
        self.assertEqual(helpers.process_params('', '', '', '', '', ''), {})
        self.assertEqual(helpers.process_params(None, None, None, None, None, None), {})

    def test_process_params_strings(self):
        """ Test strings."""
        expected = {
            k: k
            for k in ('revision', 'project', 'variant', 'task', 'test', 'thread_level')
        }
        self.assertEqual(
            helpers.process_params('revision', 'project', 'variant', 'task', 'test',
                                   'thread_level'), expected)

    def test_process_params_re_strings(self):
        """ Test re strings."""
        expected = {
            k: re.compile(k)
            for k in ('revision', 'project', 'variant', 'task', 'test', 'thread_level')
        }
        self.assertEqual(
            helpers.process_params('/revision/', '/project/', '/variant/', '/task/', '/test/',
                                   '/thread_level/'), expected)


class TestProcessExcludes(unittest.TestCase):
    """
    Test process_excludes.
    """

    def setUp(self):
        self.pattern = re.compile('string')

    def test_process_excludes_empty(self):
        """ Test empty."""
        self.assertEqual(helpers.process_excludes([]), [])

    def test_process_excludes_string(self):
        """ Test string."""
        self.assertEqual(helpers.process_excludes(['string']), [self.pattern])

    def test_process_excludes_pattern(self):
        """ Test pattern."""
        self.assertEqual(
            helpers.process_excludes(['string1', 'string2']),
            [re.compile('string1'), re.compile('string2')])


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
    Test show_label_function.
    """

    def test_show_label_function_empty(self):
        """ Test empty."""
        self.assertEqual(helpers.show_label_function(None), None)

    def test_show_label_function_string(self):
        """ Test string."""
        self.assertEqual(helpers.show_label_function(''), None)

    def test_show_label_function(self):
        """ Test expected."""
        item = {'project': 'project', 'variant': 'variant', 'task': 'task'}
        expected = 'project/variant/task'
        actual = helpers.show_label_function(item)
        self.assertEqual(expected, actual)

    def test_show_label_function_short(self):
        """ Test short."""
        item = {'project': 'project', 'variant': 'variant', 'task': 'task'}
        expected = 'variant/task'
        actual = helpers.show_label_function(item, info_width=24)
        self.assertEqual(expected, actual)

    def test_show_label_function_shorter(self):
        """ Test shorter."""
        item = {'project': 'project', 'variant': 'variant', 'task': 'task'}
        expected = 'task'
        actual = helpers.show_label_function(item, info_width=16)
        self.assertEqual(expected, actual)


class TestGetMatchingTasks(unittest.TestCase):
    """
    Test get_matching_tasks.
    """

    def test_get_matching_tasks(self):
        """ Test the core function."""
        self.assertEqual(helpers.show_label_function(None), None)
        database = mock.MagicMock(name='database')

        database.aggregate.return_value = 'expected'
        value = helpers.get_matching_tasks(database, {}, 30)
        self.assertEqual(value, 'expected')
        database.aggregate.assert_called_once()


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
