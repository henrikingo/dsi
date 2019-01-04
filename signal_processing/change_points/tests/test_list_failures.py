"""
Unit tests for signal_processing/change_points/list_failures.py.
"""

import datetime
import os
import unittest

from mock import MagicMock, patch, call

from signal_processing.change_points import list_failures
from test_lib.comparator_utils import ANY_IN_STRING
from test_lib.fixture_files import FixtureFiles

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))

NS = 'signal_processing.change_points.list_failures'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


def _filter_results(failures, show_patches=False, show_wtdevelop=False):
    if not show_patches:
        failures = [
            result for result in failures
            if '_patch_' + result['tasks'][0]['revision'] not in result['tasks'][0]['task_id']
        ]

    if not show_wtdevelop:
        failures = [
            result for result in failures if 'wtdevelop' not in result['tasks'][0]['build_variant']
        ]

    return failures


class TestListFailures(unittest.TestCase):
    """
    Test suite for list_failures method.
    """

    def setUp(self):
        fixtures = FIXTURE_FILES.load_json_file('list_failures.json')
        self.failures = fixtures['tasks']
        self.expected = fixtures['expected']

    def test_empty_list_failures(self):
        """ Test that list_failures works with no failures."""

        mock_evg_client = MagicMock(name='evg_client')
        mock_evg_client.get_project_tasks.return_value = []
        mock_config = MagicMock(name='config', compact=True)
        mock_logger = MagicMock(name='LOG')
        list_failures.LOG.info = mock_logger

        project = 'sys-perf'
        show_wtdevelop = False
        show_patches = False
        human_readable = False
        limit = None
        no_older_than = None
        evg_client = mock_evg_client
        command_config = mock_config
        list_failures.list_failures(project, show_wtdevelop, show_patches, human_readable, limit,
                                    no_older_than, evg_client, command_config)

        mock_logger.assert_called_once_with(ANY_IN_STRING('list_failures no results'))

    def test_filter(self):
        """ Test that some results are filtered."""

        mock_evg_client = MagicMock(name='evg_client')
        mock_evg_client.get_project_tasks.return_value = [{
            'status': 'failed',
            'revision': 'REVISION 1',
            'task_id': 'Group1_patch_REVISION 1',
            'build_variant': 'Variant',
            "start_time": "2018-10-13T07:26:53.001Z"
        }, {
            'status': 'failed',
            'revision': 'REVISION 2',
            'task_id': 'Group1_patch_REVISION 2',
            'build_variant': 'Variant',
            "start_time": "2018-10-13T07:26:53.002Z"
        }, {
            'status': 'failed',
            'revision': 'REVISION 3',
            'task_id': 'task_patch_REVISION 3',
            'build_variant': 'Variant',
            "start_time": "2018-10-13T07:26:53.003Z"
        }, {
            'status': 'failed',
            'revision': 'REVISION 4',
            'task_id': 'REVISION 4',
            'build_variant': 'wtdevelop_Variant',
            "start_time": "2018-10-13T07:26:53.004Z"
        }]
        mock_config = MagicMock(name='config', compact=True)
        mock_logger = MagicMock(name='LOG')
        list_failures.LOG.info = mock_logger

        project = 'sys-perf'
        show_wtdevelop = False
        show_patches = False
        human_readable = False
        limit = None
        no_older_than = None
        evg_client = mock_evg_client
        command_config = mock_config
        list_failures.list_failures(project, show_wtdevelop, show_patches, human_readable, limit,
                                    no_older_than, evg_client, command_config)

        mock_logger.assert_called_once_with(ANY_IN_STRING('list_failures no failed tests'))

    def _test_list_failures(self,
                            project='sys-perf',
                            show_wtdevelop=True,
                            show_patches=True,
                            human_readable=True,
                            limit=None,
                            no_older_than=None,
                            today=None,
                            expected=None,
                            compact=True):
        """ test helper."""
        # pylint: disable=too-many-locals

        if expected is None:
            expected = self.expected

        if today is None:
            today = datetime.date(2018, 10, 11)

        with patch(ns('stream_human_readable')) as mock_stream,\
             patch(ns('stringify_json')) as mock_stringify_json,\
             patch(ns('date')) as mock_date:

            mock_date.today.return_value = today
            mock_evg_client = MagicMock(name='evg_client')
            mock_stream.return_value = ['one']
            mock_evg_client.get_project_tasks.return_value = self.failures
            mock_config = MagicMock(name='config', compact=compact)

            evg_client = mock_evg_client
            command_config = mock_config
            list_failures.list_failures(project, show_wtdevelop, show_patches, human_readable,
                                        limit, no_older_than, evg_client, command_config)

            if human_readable:
                mock_stream.assert_called_once_with(expected)
            else:
                calls = [call(failure, compact=compact) for failure in expected]
                mock_stringify_json.assert_has_calls(calls)

    def test_no_filter(self):
        """ Test with no filters."""
        self._test_list_failures(expected=self.expected)

    def test_filter_all(self):
        """ Test with all filters."""
        self._test_list_failures(
            expected=_filter_results(self.expected), show_wtdevelop=False, show_patches=False)

    def test_limit_1(self):
        """ Test with limit 1."""
        self._test_list_failures(expected=self.expected[:1], limit=1)

    def test_limit_2(self):
        """ Test with limit 2."""
        self._test_list_failures(expected=self.expected[:2], limit=2)

    def test_all_older(self):
        """ Test all older."""
        self._test_list_failures(expected=[], today=datetime.date(2018, 10, 15), no_older_than=1)

    def test_one_older(self):
        """ Test all older."""
        self._test_list_failures(
            expected=_filter_results(self.expected)[:1],
            today=datetime.date(2018, 10, 14),
            no_older_than=1)

    def test_two_older(self):
        """ Test 2 older."""
        self._test_list_failures(
            expected=self.expected[:2], today=datetime.date(2018, 10, 14), no_older_than=2)

    def test_json(self):
        """ Test json document."""
        self._test_list_failures(expected=self.expected[:1], limit=1, human_readable=False)
