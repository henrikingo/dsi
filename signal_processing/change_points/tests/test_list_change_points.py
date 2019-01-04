"""
Unit tests for signal_processing/change_points/list_change_points.py.
"""
import re
import unittest
from collections import OrderedDict

import jinja2
import pymongo
from mock import ANY, MagicMock, patch

from signal_processing.change_points import list_change_points
from signal_processing.commands import helpers
from bin.common.log import setup_logging

setup_logging(False)

NS = 'signal_processing.change_points.list_change_points'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestMapCollection(unittest.TestCase):
    """
    Test suite for map_collection validation.
    """

    def setUp(self):
        self.mock_processed_change_points = MagicMock(name='processed_change_points')
        self.mock_unprocessed_change_points = MagicMock(name='unprocessed_change_points')
        self.mock_change_points = MagicMock(name='change_points')
        self.mock_config = MagicMock(
            name='config',
            processed_change_points=self.mock_processed_change_points,
            unprocessed_change_points=self.mock_unprocessed_change_points,
            change_points=self.mock_change_points)

    def test_map_invalid(self):
        """ Test list unprocessed."""
        self.assertRaisesRegexp(
            ValueError,
            'war is not a valid change point type.',
            list_change_points.map_collection,
            'war',
            command_config=None)

    def test_map_unprocessed(self):
        """ Test list unprocessed."""
        self.assertEquals(self.mock_unprocessed_change_points,
                          list_change_points.map_collection(
                              list_change_points.CHANGE_POINT_TYPE_UNPROCESSED, self.mock_config))

    def test_map_processed(self):
        """ Test list processed."""
        self.assertEquals(self.mock_processed_change_points,
                          list_change_points.map_collection(
                              list_change_points.CHANGE_POINT_TYPE_PROCESSED, self.mock_config))

    def test_map_raw(self):
        """ Test list raw."""
        self.assertEquals(self.mock_change_points,
                          list_change_points.map_collection(
                              list_change_points.CHANGE_POINT_TYPE_RAW, self.mock_config))


class TestListChangePoints(unittest.TestCase):
    """
    Test suite to check the correct collection is selected for list_change_points.
    """

    def setUp(self):
        self.mock_aggregate = MagicMock(name='unprocessed aggregate')
        self.mock_unprocessed_change_points = MagicMock(name='unprocessed_change_points')
        self.mock_unprocessed_change_points.aggregate = self.mock_aggregate
        self.mock_config = MagicMock(
            name='config', unprocessed_change_points=self.mock_unprocessed_change_points)

    def _test_helper(self, human_readable, mock_create_pipeline, mock_filter,
                     mock_stream_human_readable):
        """ test list_change_points helper."""

        list_change_points.list_change_points(
            list_change_points.CHANGE_POINT_TYPE_UNPROCESSED,
            query={'find': 'me'},
            limit='limit',
            no_older_than='no_older_than',
            human_readable=human_readable,
            hide_canaries='canaries',
            hide_wtdevelop='wtdevelop',
            exclude_patterns='excludes',
            processed_types=[helpers.PROCESSED_TYPE_ACKNOWLEDGED],
            command_config=self.mock_config)

        mock_collection = self.mock_unprocessed_change_points

        mock_create_pipeline.assert_called_once_with({
            'find': 'me'
        }, 'limit', 'canaries', 'wtdevelop', 'no_older_than')
        mock_collection.aggregate.assert_called_once_with('pipeline')
        mock_filter.assert_called_once_with(ANY, ['find'], 'excludes')
        if human_readable:
            mock_stream_human_readable.assert_called_once_with('filtered_cursor', mock_collection,
                                                               'limit', 'no_older_than')
        else:
            mock_stream_human_readable.assert_not_called()

    @patch(ns('stream_human_readable'))
    @patch(ns('filter_excludes'), return_value='filtered_cursor')
    @patch(ns('create_pipeline'), return_value='pipeline')
    def test_list_change_points(self, mock_create_pipeline, mock_filter,
                                mock_stream_human_readable):
        """ test list_change_points human readable."""
        self._test_helper(True, mock_create_pipeline, mock_filter, mock_stream_human_readable)

    @patch(ns('stream_human_readable'))
    @patch(ns('filter_excludes'), return_value=[])
    @patch(ns('create_pipeline'), return_value='pipeline')
    def test_list_change_points_not(self, mock_create_pipeline, mock_filter,
                                    mock_stream_human_readable):
        """ test list_change_points not human readable."""
        self._test_helper(False, mock_create_pipeline, mock_filter, mock_stream_human_readable)


class TestRender(unittest.TestCase):
    """
    Test suite for stream_human_readable.
    """

    def _test_render_date(self, mock_template, no_older):
        """ test helper."""
        mock_collection = MagicMock(name="collection")
        if no_older:
            no_older_than = MagicMock(name="datetime")
            no_older_than.date.return_value = 'date'
        else:
            no_older_than = None
        list_change_points.stream_human_readable('points', mock_collection, 'limit', no_older_than)
        mock_template.stream.assert_called_once_with(
            points='points', collection=mock_collection, limit='limit', no_older_than=no_older_than)

    @patch(ns('HUMAN_READABLE_TEMPLATE'))
    def test_render_no_date(self, mock_template):
        """ test list_change_points helper."""
        self._test_render_date(mock_template, True)

    @patch(ns('HUMAN_READABLE_TEMPLATE'))
    def test_render_date(self, mock_template):
        """ test list_change_points helper."""
        self._test_render_date(mock_template, False)


class TestPipeline(unittest.TestCase):
    """
    Test suite for create_pipeline.
    """

    def _pipeline(self,
                  query=None,
                  limit=10,
                  hide_canaries=True,
                  hide_wtdevelop=True,
                  no_older_than=None):
        """
        Helper function for pipeline testing.

        :param dict query: The query, defaults to {'find': 'me'} when None.
        :param int limit: The limit value.
        :param bool hide_canaries: The hide canaries value.
        :param bool hide_wtdevelop: The hide wtdevelop value.
        :param int not_older_than: The no older than value.
        :return: The pipeline.
        :rtype: list(dict).
        """
        if query is None:
            query = {'find': 'me'}
        return list_change_points.create_pipeline(query, limit, hide_canaries, hide_wtdevelop,
                                                  no_older_than)

    def test_pipeline(self):
        """ test create_pipeline."""
        limit = 10
        pipeline = self._pipeline(limit=limit)
        self.assertTrue({
            '$addFields': {
                'start': {
                    '$ifNull': ["$start", {
                        '$dateFromString': {
                            'dateString': '$create_time'
                        }
                    }]
                }
            }
        } in pipeline)

        self.assertTrue({'$match': {'find': 'me'}} in pipeline)

        self.assertTrue({
            '$match': {
                'test': {
                    '$not': re.compile('^(canary_|fio_|NetworkBandwidth)')
                }
            }
        } in pipeline)

        self.assertTrue({'$match': {'variant': {'$not': re.compile('^wtdevelop')}}} in pipeline)
        self.assertTrue({'$limit': limit} in pipeline)
        self.assertTrue({'$sort': OrderedDict([('min_magnitude', pymongo.ASCENDING)])} in pipeline)

    def test_show_canaries(self):
        """ test create_pipeline show canaries."""
        pipeline = self._pipeline(hide_canaries=False)
        self.assertTrue({
            '$match': {
                'test': {
                    '$not': re.compile('^(canary_|fio_|NetworkBandwidth)')
                }
            }
        } not in pipeline)

    def test_show_wtdevelop(self):
        """ test create_pipeline show wtdevelop."""
        pipeline = self._pipeline(hide_wtdevelop=False)
        self.assertTrue({'$match': {'variant': {'$not': re.compile('^wtdevelop')}}} not in pipeline)

    def test_no_limit(self):
        """ test no no, no no, no no, theres no limits!."""
        pipeline = self._pipeline(limit=None)
        self.assertTrue('$limit' not in pipeline[-1].keys())


class TestMagnitudeToPercent(unittest.TestCase):
    """
    Test suite for magnitude_to_percent.
    """

    def test_not_float(self):
        """ test some unexpected types."""
        self.assertEquals('Nan', list_change_points.magnitude_to_percent(
            jinja2.runtime.Undefined()))
        self.assertEquals('Nan', list_change_points.magnitude_to_percent(None))

    def test_float(self):
        """ test some float values."""
        self.assertEquals('+11%', list_change_points.magnitude_to_percent(0.1))
        self.assertEquals('-10%', list_change_points.magnitude_to_percent(-0.1))
        self.assertEquals('+172%', list_change_points.magnitude_to_percent(1.0))
        self.assertEquals('-63%', list_change_points.magnitude_to_percent(-1.0))

    def test_float_format(self):
        """ test some float values with non default format."""
        self.assertEquals('+10.52%', list_change_points.magnitude_to_percent(0.1, '%+5.2f%%'))
        self.assertEquals('-9.52%', list_change_points.magnitude_to_percent(-0.1, '%+5.2f%%'))
        self.assertEquals('+171.83%', list_change_points.magnitude_to_percent(1.0, '%+5.2f%%'))
        self.assertEquals('-63.21%', list_change_points.magnitude_to_percent(-1.0, '%+5.2f%%'))


class TestToLink(unittest.TestCase):
    """
    Test suite for to_link.
    """

    def test_to_link(self):
        """ test basic operation."""
        self.assertEquals('EVG/version/PROJECT_REVISION',
                          list_change_points.to_link({
                              'project': 'PROJECT',
                              'suspect_revision': 'REVISION'
                          }, 'EVG'))


class TestToTaskLink(unittest.TestCase):
    """
    Test suite for to_task_link.
    """

    def test_to_task_link(self):
        """ test basic operation."""
        self.assertEquals('EVG/task/TASK_ID',
                          list_change_points.to_task_link({
                              'task_id': 'TASK_ID'
                          }, 'EVG'))
