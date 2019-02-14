"""
Unit tests for signal_processing/outliers/mute.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function

from StringIO import StringIO
import unittest

from mock import MagicMock, patch, call

from signal_processing.outliers.list_mutes import list_mutes, create_pipeline, \
    stream_human_readable

NS = 'signal_processing.outliers'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestStreamHumanReadable(unittest.TestCase):
    """ Test stream_human_readable. """

    def test_stream_human_readable(self):
        """ test stream_human_readable. """
        with patch(ns('list_mutes.HUMAN_READABLE_TEMPLATE')) as mock_stream:
            mutes = {'_id': 'id', 'mutes': ['mute 0', 'mute 1']}
            mock_collection = MagicMock(name='collection')
            mock_points_collection = MagicMock(name='points_collection')
            limit = 'limit'
            no_older_than = 'no_older_than'
            stream_human_readable(mutes, mock_collection, mock_points_collection, limit,
                                  no_older_than)
            mock_stream.stream.assert_called_once_with(
                _id='id',
                mutes=['mute 0', 'mute 1'],
                collection=mock_collection,
                points_collection=mock_points_collection,
                limit=limit,
                no_older_than=no_older_than)


class TestCreatePipeline(unittest.TestCase):
    """ Test create_pipeline. """

    def _test_create_pipeline(self, limit=None, no_older_than=None):
        """ create_pipeline Test  helper. """

        query = {'project': 'sys-perf'}

        pipeline = create_pipeline(query, limit, no_older_than)
        stage = pipeline.pop(0)
        if no_older_than is not None:
            self.assertIn('create_time', stage['$match'])
            stage = pipeline.pop(0)
        self.assertDictEqual(query, stage['$match'])

        stage = pipeline.pop(0)
        self.assertIn('$sort', stage)

        stage = pipeline.pop(0)
        self.assertIn('$group', stage)

        stage = pipeline.pop(0)
        self.assertIn('$project', stage)

        stage = pipeline.pop(0)
        self.assertIn('$sort', stage)

        if limit is not None:
            stage = pipeline.pop(0)
            self.assertIn('$limit', stage)
        self.assertTrue(pipeline == [])

    def test_create_pipeline(self):
        """ Test create_pipeline, """
        self._test_create_pipeline()

    def test_create_pipeline_limit(self):
        """ Test create_pipeline, """
        self._test_create_pipeline(limit=1)

    def test_create_pipeline_older(self):
        """ Test create_pipeline, """
        self._test_create_pipeline(no_older_than=1)

    def test_create_pipeline_limit_and_older(self):
        """ Test create_pipeline, """
        self._test_create_pipeline(limit=1, no_older_than=1)


class TestListMutes(unittest.TestCase):
    """ Test list_mutes. """

    def test_no_mutes(self):
        """ Test list_mutes, """

        with patch(ns('list_mutes.stream_human_readable')) as mock_stream_human_readable,\
             patch(ns('list_mutes.create_pipeline')) as mock_create_pipeline:

            pipeline = ['1', 2, 'three']
            mock_create_pipeline.return_value = pipeline
            mock_mute_outliers = MagicMock(name='mute_outliers')
            mock_config = MagicMock(name='config', mute_outliers=mock_mute_outliers)
            query = {'project': 'sys-perf'}
            human_readable = True
            limit = None
            no_older_than = None
            list_mutes(query, human_readable, limit, no_older_than, mock_config)
            mock_stream_human_readable.assert_not_called()
            mock_create_pipeline.assert_called_once_with(query, limit, no_older_than)
            mock_mute_outliers.aggregate.assert_called_once_with(pipeline)

    def _test_mutes(self, human_readable=True):
        # pylint: disable=too-many-locals
        stream = [('first', 'second'), ('third', 'fourth')]
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout, \
             patch(ns('list_mutes.stream_human_readable')) as mock_stream_human_readable,\
             patch(ns('list_mutes.create_pipeline')) as mock_create_pipeline,\
             patch(ns('list_mutes.stringify_json')) as mock_stringify_json:

            pipeline = ['1', 2, 'three']
            mock_create_pipeline.return_value = pipeline
            mock_mute_outliers = MagicMock(name='mute_outliers')
            mock_points = MagicMock(name='points')
            mock_config = MagicMock(
                name='config', mute_outliers=mock_mute_outliers, points=mock_points)
            query = {'project': 'sys-perf'}
            limit = None
            no_older_than = None

            mock_mute_outliers.aggregate.return_value = range(2)
            mock_stream_human_readable.side_effect = stream
            list_mutes(query, human_readable, limit, no_older_than, mock_config)
            mock_create_pipeline.assert_called_once_with(query, limit, no_older_than)
            mock_mute_outliers.aggregate.assert_called_once_with(pipeline)

            if human_readable:
                calls = [
                    call(i, mock_mute_outliers, mock_points, limit, no_older_than) for i in range(2)
                ]
                mock_stream_human_readable.assert_has_calls(calls, any_order=True)
                expected = ''.join([i for j in stream for i in j])
                self.assertIn(expected, mock_stdout.getvalue())
                mock_stringify_json.assert_not_called()
            else:
                mock_stringify_json.assert_called()

    def test_mutes_human(self):
        """ Test list_mutes human readable. """
        self._test_mutes()

    def test_mutes_not_human(self):
        """ Test list_mutes human readable. """
        self._test_mutes(human_readable=False)
