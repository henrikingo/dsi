"""
Unit tests for signal_processing/outliers/mute.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function

import jinja2
import unittest
from datetime import datetime, tzinfo, timedelta

from mock import MagicMock, PropertyMock

from signal_processing.util.format_util import format_datetime, to_point_query, to_task_link, \
    to_version_link, to_project_link, format_limit, format_no_older_than, to_change_point_query, \
    magnitude_to_percent

NS = 'signal_processing.outliers'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestFormatNoOlderThan(unittest.TestCase):
    """ Test format_no_older_than. """

    def test_format_no_older_than(self):
        """ test format_no_older_than. """
        self.assertEquals('All', format_no_older_than(None))
        self.assertEquals('Last 1 days', format_no_older_than('1'))


class TestFormatLimit(unittest.TestCase):
    """ Test format_limit. """

    def test_format_limit(self):
        """ test format_limit. """
        self.assertEquals('All', format_limit(None))
        self.assertEquals('UpTo 1', format_limit('1'))


class TestToTaskLink(unittest.TestCase):
    """ Test to_task_link. """

    def test_to_task_link(self):
        """ test to_task_link. """
        task_id = 'sys_perf_wtdevelop_3_node_replSet_bestbuy_agg_302a4f91a54a77221f7408b95fcbb988a9366d03_19_02_11_21_21_07'
        test = {'task_id': task_id}
        evergreen = 'http://evergreen'
        expected = "{}/task/{}".format(evergreen, task_id)
        self.assertEquals(expected, to_task_link(test, evergreen))


class TestToProjectLink(unittest.TestCase):
    """ Test to_project_link. """

    def test_to_task_link(self):
        """ test to_task_link. """
        project_id = 'sys-perf'
        test = {'project_id': project_id}
        evergreen = 'http://evergreen'
        expected = "{}/waterfall/{}".format(evergreen, project_id)
        self.assertEquals(expected, to_project_link(test, evergreen))


class TestToVersionLink(unittest.TestCase):
    """ Test to_version_link. """

    def test_to_version_link(self):
        """ test to_task_link. """
        version_id = 'sys_perf_302a4f91a54a77221f7408b95fcbb988a9366d03'
        test = {'version_id': version_id}
        evergreen = 'http://evergreen'
        expected = "{}/version/{}".format(evergreen, version_id)
        self.assertEquals(expected, to_version_link(test, evergreen))


class TestToPointQuery(unittest.TestCase):
    """ Test to_point_query. """

    def test_to_point_query(self):
        """ test to_point_query. """
        mock_collection = MagicMock(name='collection')
        p = PropertyMock(return_value='outliers')
        type(mock_collection).name = p
        test = {
            'project': 'sys-perf',
            'variant': 'linux-standalone',
            'task': 'bestbuy_agg',
            'test': 'distinct_types_no_predicate-useAgg',
            'thread_level': '1',
            'revision': '80f9a13324fc36b2deb400e5a185968f6fa8f64a'
        }

        expected = "db.outliers.find({project: 'sys-perf', variant: 'linux-standalone', "\
                   "task: 'bestbuy_agg', test: 'distinct_types_no_predicate-useAgg', "\
                   "thread_level: '1', revision: '80f9a13324fc36b2deb400e5a185968f6fa8f64a'})"
        self.assertEquals(expected, to_point_query(test, mock_collection))


class TestToChangePointQuery(unittest.TestCase):
    """ Test to_change_point_query. """

    def test_to_change_point_query(self):
        """ test to_change_point_query. """
        mock_collection = MagicMock(name='collection')
        p = PropertyMock(return_value='change_points')
        type(mock_collection).name = p
        test = {
            'project': 'sys-perf',
            'variant': 'linux-standalone',
            'task': 'bestbuy_agg',
            'test': 'distinct_types_no_predicate-useAgg',
            'thread_level': '1',
            'suspect_revision': '80f9a13324fc36b2deb400e5a185968f6fa8f64a'
        }

        expected = "db.change_points.find({project: 'sys-perf', "\
                   "suspect_revision: '80f9a13324fc36b2deb400e5a185968f6fa8f64a'})"
        self.assertEquals(expected, to_change_point_query(test, mock_collection))


class TestFormatDate(unittest.TestCase):
    """ Test format_datetime. """

    def test_format_datetime(self):
        """ test format_datetime. """
        self.assertEquals('1970-01-01T00:00:00Z', format_datetime(0))
        self.assertEquals('1970-01-01T00:00:01Z', format_datetime(1.0))
        self.assertEquals('1970-01-01T00:00:02Z', format_datetime(datetime.utcfromtimestamp(2)))

        class Eastern(tzinfo):
            """ US/Eastern timezone, Don't want to add a dependency on pytz. """

            def utcoffset(self, dt):
                return timedelta(hours=-5) + self.dst(dt)

            def dst(self, dt):
                return timedelta(0)

            def tzname(self, dt):
                return "US/Eastern"

        time = datetime.fromtimestamp(2, tz=Eastern())
        self.assertEquals('1969-12-31T19:00:02Z', format_datetime(time))


class TestMagnitudeToPercent(unittest.TestCase):
    """ Test magnitude_to_percent. """

    def test_magnitude_to_percent(self):
        """ test magnitude_to_percent. """
        self.assertEquals('Nan', magnitude_to_percent(None))
        self.assertEquals('Nan', magnitude_to_percent(jinja2.runtime.Undefined()))
        self.assertEquals('+172%', magnitude_to_percent(1.0))
