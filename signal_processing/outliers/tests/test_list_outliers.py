"""
Unit tests for signal_processing/outliers/list_outliers.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function

from StringIO import StringIO
import unittest

from mock import MagicMock, patch, call

from signal_processing.outliers.list_outliers import stream_human_readable, create_pipeline, \
    list_outliers

NS = 'signal_processing.outliers'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestStreamHumanReadable(unittest.TestCase):
    """ Test stream_human_readable. """

    def test_stream_human_readable(self):
        """ test stream_human_readable. """
        with patch(ns('list_outliers.HUMAN_READABLE_TEMPLATE')) as mock_stream:
            outliers = {'_id': 'id', 'outliers': ['outlier 0', 'outlier 1']}
            mock_collection = MagicMock(name='collection')
            limit = 'limit'
            no_older_than = 'no_older_than'
            stream_human_readable(outliers, mock_collection, limit, no_older_than)
            mock_stream.stream.assert_called_once_with(
                _id='id',
                outliers=outliers['outliers'],
                collection=mock_collection,
                limit=limit,
                no_older_than=no_older_than)


class TestCreatePipeline(unittest.TestCase):
    """ Test create_pipeline. """

    def _test_create_pipeline(self, marked=False, types=None, limit=None, no_older_than=None):
        """ create_pipeline Test  helper. """

        query = {'project': 'sys-perf'}

        pipeline = create_pipeline(query, marked, types, limit, no_older_than)

        stage = pipeline.pop(0)
        if no_older_than is not None:
            self.assertIn('create_time', stage['$match'])
            stage = pipeline.pop(0)
        self.assertDictEqual(query, stage['$match'])

        stage = pipeline.pop(0)
        if not marked and types:
            self.assertEqual(types, stage['$match']['type']['$in'])
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

    def test_create_pipeline_with_types(self):
        self._test_create_pipeline(types=['type 1', 'type 2'])

    def test_create_pipeline_with_types_and_marked(self):
        self._test_create_pipeline(marked=True, types=['type 1', 'type 2'])


class TestListOutliers(unittest.TestCase):
    """ Test list_outliers. """

    def test_no_outliers(self):
        """ Test list_outliers, """

        with patch(ns('list_outliers.stream_human_readable')) as mock_stream_human_readable,\
             patch(ns('list_outliers.create_pipeline')) as mock_create_pipeline:

            pipeline = ['1', 2, 'three']
            mock_create_pipeline.return_value = pipeline
            mock_outliers = MagicMock(name='mock_outliers')
            mock_config = MagicMock(name='config', outliers=mock_outliers)
            query = {'project': 'sys-perf'}
            human_readable = True
            limit = None
            no_older_than = None
            marked = False
            types = ['type 1', ['type 2']]
            list_outliers(query, marked, types, human_readable, limit, no_older_than, mock_config)
            mock_stream_human_readable.assert_not_called()
            mock_create_pipeline.assert_called_once_with(query, marked, types, limit, no_older_than)
            mock_outliers.aggregate.assert_called_once_with(pipeline)

    def _test_outliers(self, human_readable=True, marked=False):
        # pylint: disable=too-many-locals
        stream = [('first', 'second'), ('third', 'fourth')]
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout, \
             patch(ns('list_outliers.stream_human_readable')) as mock_stream_human_readable,\
             patch(ns('list_outliers.create_pipeline')) as mock_create_pipeline,\
             patch(ns('list_outliers.stringify_json')) as mock_stringify_json:

            pipeline = ['1', 2, 'three']
            mock_create_pipeline.return_value = pipeline
            mock_outliers = MagicMock(name='outliers')
            mock_marked_outliers = MagicMock(name='marked_outliers')
            mock_config = MagicMock(
                name='config', outliers=mock_outliers, marked_outliers=mock_marked_outliers)
            query = {'project': 'sys-perf'}
            limit = None
            no_older_than = None
            types = ['type 1', ['type 2']]

            mock_outliers.aggregate.return_value = range(2)
            mock_marked_outliers.aggregate.return_value = range(2)
            mock_stream_human_readable.side_effect = stream
            list_outliers(query, marked, types, human_readable, limit, no_older_than, mock_config)
            mock_create_pipeline.assert_called_once_with(query, marked, types, limit, no_older_than)
            expected_collection = mock_outliers
            if marked:
                expected_collection = mock_marked_outliers

            expected_collection.aggregate.assert_called_once_with(pipeline)

            if human_readable:
                calls = [call(i, expected_collection, limit, no_older_than) for i in range(2)]
                mock_stream_human_readable.assert_has_calls(calls, any_order=True)
                expected = ''.join([i for j in stream for i in j])
                self.assertIn(expected, mock_stdout.getvalue())
                mock_stringify_json.assert_not_called()
            else:
                mock_stringify_json.assert_called()

    def test_outliers_human(self):
        """ Test list_outliers human readable. """
        self._test_outliers()

    def test_outliers_human_marked(self):
        """ Test list_outliers human readable. """
        self._test_outliers(marked=True)

    def test_mutes_not_human(self):
        """ Test list_outliers human readable. """
        self._test_outliers(human_readable=False)

    def test_mutes_not_human_on_marked(self):
        """ Test list_outliers human readable. """
        self._test_outliers(human_readable=False, marked=True)
