"""
Unit tests for signal_processing/outliers/whitelist_task.py.
"""
from __future__ import print_function

import re
import unittest
from collections import OrderedDict
from datetime import datetime

from bson import ObjectId
from mock import MagicMock, patch, call

from signal_processing.outliers.whitelist_task import whitelist_identifier, \
    stream_human_readable, _create_object_id, create_pipeline, list_whitelist, add_whitelist, \
    remove_whitelist, to_whitelist_query

NS = 'signal_processing.outliers.whitelist_task'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestToTestIdentifier(unittest.TestCase):
    """ Test to_test_identifier. """

    def _test(self, test_identifier=None, expected=None):
        if test_identifier is None:
            test_identifier = {
                'revision': '7e700f6668fcbd5b96d46884364f1a7377945abb',
                'project': 'sys-perf',
                'variant': 'linux-standalone',
                'task': 'bestbuy_agg'
            }
        if expected is None:
            expected = test_identifier
        self.assertEquals(expected, whitelist_identifier(test_identifier))

    def test_full(self):
        """ to_test_identifier with full data. """
        self._test()

    def test_extras(self):
        """ to_test_identifier to test. """
        expected = {
            'revision': '7e700f6668fcbd5b96d46884364f1a7377945abb',
            'project': 'sys-perf',
            'variant': 'linux-standalone',
            'task': 'bestbuy_agg'
        }
        test_identifier = dict(random='extra', **expected)
        self._test(test_identifier, expected)


class TestStreamHumanReadable(unittest.TestCase):
    """ Test stream_human_readable. """

    def test_full(self):
        """ to_test_identifier with full data. """
        with patch(ns('HUMAN_READABLE_TEMPLATE')) as template_mock:
            self.assertEqual(
                stream_human_readable('whitelists', 'collection', 'limit', 'no_older_than'),
                template_mock.stream.return_value)
        template_mock.stream.assert_called_once_with(
            whitelists='whitelists',
            collection='collection',
            limit='limit',
            no_older_than='no_older_than')


class TestCreateObjectId(unittest.TestCase):
    """ Test _create_object_id. """

    def test_create_object_id(self):
        """ test _create_object_id 8 days. """
        year = 2019
        month = 4
        day = 8
        now_mock = MagicMock(name='utcnow')
        with patch(ns('datetime')) as datetime_mock:
            datetime_mock.utcnow.return_value = now_mock
            datetime_mock.return_value = datetime(year, month, day)
            self.assertEqual(_create_object_id(8), ObjectId('5ca003000000000000000000'))
        datetime_mock.assert_called_once_with(
            now_mock.year, now_mock.month, now_mock.day, tzinfo=now_mock.tzinfo)


class TestToWhitelistQuery(unittest.TestCase):
    """ Test to_whitelist_query. """

    def test_to_whitelist_query(self):
        """ Test to_whitelist_query. """
        collection_mock = MagicMock(name='whitelist')
        collection_mock.name = 'whitelist'
        whitelist = {
            'revision': '7e700f6668fcbd5b96d46884364f1a7377945abb',
            'project': 'sys-perf',
            'variant': 'linux-standalone',
            'task': 'bestbuy_agg',
        }
        expected = "db.whitelist.find({revision: '7e700f6668fcbd5b96d46884364f1a7377945abb', " \
                   "project: 'sys-perf', " \
                   "variant: 'linux-standalone', task: 'bestbuy_agg'})"

        actual = to_whitelist_query(whitelist, collection_mock)
        self.assertEqual(expected, actual)


class TestCreatePipeline(unittest.TestCase):
    """ Test create_pipeline. """

    def _test_create_pipeline(self, limit=None, no_older_than=None, hide_wtdevelop=True):
        """ create_pipeline Test helper. """

        query = {'project': 'sys-perf'}
        oid = 'OBJECTID'
        with patch(ns('_create_object_id'), return_value=oid):
            pipeline = create_pipeline(query, limit, no_older_than, hide_wtdevelop)
        stage = pipeline.pop(0)
        if no_older_than is not None:
            self.assertDictEqual(stage, {'$match': {'_id': {"$gte": oid}}})
            stage = pipeline.pop(0)

        if hide_wtdevelop:
            self.assertDictEqual(stage, {'$match': {'variant': {'$not': re.compile('^wtdevelop')}}})
            stage = pipeline.pop(0)

        self.assertDictEqual(stage, {'$match': query})

        stage = pipeline.pop(0)
        self.assertDictEqual(stage, {'$sort': OrderedDict([('order', -1)])})

        if limit is not None:
            stage = pipeline.pop(0)
            self.assertDictEqual(stage, {'$limit': limit})
        self.assertTrue(pipeline == [])

    def test(self):
        """ Test create_pipeline defaults, """
        self._test_create_pipeline()

    def test_limit(self):
        """ Test create_pipeline with limit, """
        self._test_create_pipeline(limit=1)

    def test_older(self):
        """ Test create_pipeline with no older, """
        self._test_create_pipeline(no_older_than=1)

    def test_show_wtdevelop(self):
        """ Test create_pipeline show wtdevelop, """
        self._test_create_pipeline(hide_wtdevelop=False)

    def test_limit_and_older(self):
        """ Test create_pipeline limit and no older, """
        self._test_create_pipeline(limit=1, no_older_than=1)


class TestListWhitelist(unittest.TestCase):
    """ Test list_whitelist. """

    # pylint: disable=no-self-use
    def _test(self,
              cursor=False,
              limit=5,
              no_older_than=10,
              human_readable=True,
              show_wtdevelop=False):
        model_mock = MagicMock(name='model', collection='collection')
        layers = [] if not cursor else ['configuration']
        model_mock.get_configuration.return_value = layers
        command_config_mock = MagicMock(name='command_config')
        collection_mock = command_config_mock.whitelisted_outlier_tasks
        if cursor:
            data = iter([1])
        else:
            data = iter([])
        collection_mock.aggregate.return_value = data
        test_identifier = {'project': 'sys-perf'}

        with patch(ns('create_pipeline')),\
             patch(ns('stringify_json'), return_value="json") as stringify_json_mock,\
             patch(ns('stream_human_readable')) as stream_mock:
            stream_human_readable.return_value = data
            list_whitelist(test_identifier, limit, no_older_than, human_readable, show_wtdevelop,
                           command_config_mock)
        if human_readable:
            stream_mock.assert_called_once_with(data, collection_mock, limit, no_older_than)
        else:
            if cursor:
                stringify_json_mock.assert_called_with(1, compact=command_config_mock.compact)
            else:
                stringify_json_mock.assert_not_called()

    def test_human_readable(self):
        """ test with no data. """
        self._test()

    def test_human_readable_data(self):
        """ test with with data. """
        self._test(cursor=True)

    def test_not_human_readable(self):
        """ test with not human_readable , no data. """
        self._test(human_readable=False)

    def test_not_human_readable_data(self):
        """ test with with nothuman_readable,  data. """
        self._test(cursor=True, human_readable=False)


class TestAddWhitelist(unittest.TestCase):
    """ Test add_whitelist. """

    def _test_add_whitelist(self, dry_run=False, exception=False):
        """ Test add_whitelist helper. """
        # pylint: disable=too-many-locals
        collection_mock = MagicMock(name='whitelisted_outlier_tasks')
        command_config_mock = MagicMock(
            name='command_config', whitelisted_outlier_tasks=collection_mock, dry_run=dry_run)

        task_identifier = {'project': 'sys-perf'}
        with patch(ns('get_whitelists'), autospec=True) as get_whitelists_mock, \
             patch(ns('pymongo.UpdateOne'), autospec=True) as update_mock,\
             patch(ns('whitelist_identifier'), autospec=True) as whitelist_identifier_mock:

            mock_client = collection_mock.database.client
            mock_session = mock_client.start_session.return_value.__enter__.return_value

            task_revisions = ['first', 'second', 'third']
            get_whitelists_mock.return_value = task_revisions

            identifiers = ['first', 'second', 'third']
            whitelist_identifier_mock.side_effect = identifiers

            requests = ['foo', 'bar', 'baz']
            update_mock.side_effect = requests

            if exception:
                collection_mock.bulk_write.side_effect = Exception('Boom!')
                self.assertRaises(Exception, add_whitelist, task_identifier, command_config_mock)
            else:
                add_whitelist(task_identifier, command_config_mock)
            if not dry_run:
                mock_session.start_transaction.return_value.__enter__.assert_called_once()
                collection_mock.bulk_write.assert_called_once_with(requests, ordered=False)
            else:
                mock_session.start_transaction.return_value.__enter__.assert_not_called()
                collection_mock.bulk_write.assert_not_called()
            calls = [
                call(identifier, {'$set': task_revisions[i]}, upsert=True)
                for i, identifier in enumerate(identifiers)
            ]
            update_mock.assert_has_calls(calls)

    def test_add_whitelist_exception(self):
        """ Test add_whitelist. """
        self._test_add_whitelist(exception=True)

    def test_add_whitelist(self):
        """ Test add_whitelist. """
        self._test_add_whitelist()

    def test_add_whitelist_dryrun(self):
        """ Test add_whitelist. """
        self._test_add_whitelist(dry_run=True)


class TestRemoveWhitelist(unittest.TestCase):
    """ Test remove_whitelist. """

    def _test_remove_whitelist(self, dry_run=False, exception=False):
        """ Test remove_whitelist helper. """
        # pylint: disable=too-many-locals

        collection_mock = MagicMock(name='whitelisted_outlier_tasks')
        command_config_mock = MagicMock(
            name='command_config', whitelisted_outlier_tasks=collection_mock, dry_run=dry_run)

        task_identifier = {'project': 'sys-perf'}
        with patch(ns('get_whitelists'), autospec=True) as get_whitelists_mock, \
             patch(ns('pymongo.DeleteOne'), autospec=True) as delete_mock,\
             patch(ns('whitelist_identifier'), autospec=True) as whitelist_identifier_mock:

            mock_client = collection_mock.database.client
            mock_session = mock_client.start_session.return_value.__enter__.return_value

            task_revisions = ['first', 'second', 'third']
            get_whitelists_mock.return_value = task_revisions

            identifiers = ['first', 'second', 'third']
            whitelist_identifier_mock.side_effect = identifiers

            requests = ['foo', 'bar', 'baz']
            delete_mock.side_effect = requests

            if exception:
                collection_mock.bulk_write.side_effect = Exception('Boom!')
                self.assertRaises(Exception, remove_whitelist, task_identifier, command_config_mock)
            else:
                remove_whitelist(task_identifier, command_config_mock)
            if not dry_run:
                mock_session.start_transaction.return_value.__enter__.assert_called_once()
                collection_mock.bulk_write.assert_called_once_with(requests, ordered=False)
            else:
                mock_session.start_transaction.return_value.__enter__.assert_not_called()
                collection_mock.bulk_write.assert_not_called()
            calls = [call(identifier) for identifier in identifiers]
            delete_mock.assert_has_calls(calls)

    def test_exception(self):
        """ Test remove_whitelist exception. """
        self._test_remove_whitelist(exception=True)

    def test(self):
        """ Test remove_whitelist. """
        self._test_remove_whitelist()

    def test_dryrun(self):
        """ Test remove whitelist dryrun. """
        self._test_remove_whitelist(dry_run=True)
