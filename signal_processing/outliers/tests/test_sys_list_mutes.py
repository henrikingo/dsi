"""
Unit tests for signal_processing/outliers/mute.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function

import os
import shutil
import sys
import tempfile
import unittest
from StringIO import StringIO
from time import sleep

import bson
import structlog
from dateutil import parser as date_parser
from nose.plugins.attrib import attr
from pymongo import MongoClient

from signal_processing.outliers.list_mutes import mute_expired
from test_lib.fixture_files import FixtureFiles

NS = 'signal_processing.outliers'
SYS_FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__), is_unittest=False)
LOG = structlog.getLogger(__name__)


def enable_system_test():  # pylint: disable=invalid-name
    """
    Check if system tests should run.

    :return: True if DSI_SYSTEM_TEST env var is set to anything.
    """
    return 'DSI_SYSTEM_TEST' in os.environ


# pylint: disable=too-many-arguments
def fixture_path(name,
                 project='sys-perf',
                 variant='linux-1-node-replSet',
                 task='bestbuy_query',
                 test='canary_client-cpuloop-10x',
                 thread_level='4'):
    """
    Get the fixture path.

    :parameter str name: The fully qualified test name. The last part is expected to be prefixed
    with 'test_' and this is removed.
    :parameter str project: The project name.
    :parameter str variant: The variant name.
    :parameter str task: The task name.
    :parameter str test: The (performance) test name.
    :parameter str thread_level: The thread level.
    """
    parts = name.split('.')
    last_part = parts[-1]
    suffix = last_part[len('test_'):]
    filename = suffix + '.json'
    filename_path = os.path.join(project, variant, task, test, thread_level, filename)
    return filename_path


def load(loader, test_name, points_collection, mutes_collection):
    """
    load fixtures and save to collections.

    :parameter FixtureFiles loader: fixture loader.
    :parameter str test_name: The fully qualified test name.
    :parameter pymongo.Collection points_collection: The points collection.
    :parameter pymongo.Collection mutes_collection: The mutes collection.
    """
    fixture = loader.load_json_file(fixture_path(test_name))
    mutes = fixture.get('mutes')
    if mutes:

        def update_mutes(mute_list):
            for mute in mute_list:
                mute['_id'] = bson.ObjectId(mute['_id'])
                mute['last_updated_at'] = date_parser.parse(mute['last_updated_at'])

            return mutes_collection.insert_many(mute_list)

        current = mutes.get('current')
        results = update_mutes([current])

        before = mutes.get('before')
        if before is not None:
            update_mutes(before)

        after = mutes.get('after')
        if after is not None:
            update_mutes(after)

        mute_id = results.inserted_ids[0]
        mute = mutes_collection.find_one({'_id': mute_id})
    else:
        mute = None
    points = fixture.get('points')
    if points:

        def update(after):
            if after:
                for point in after:
                    point['_id'] = bson.ObjectId(point['_id'])
                points_collection.insert_many(after)

        current = points.get('current')
        if current is not None:
            update([current])
        update(points.get('after'))
        update(points.get('before'))
    return fixture, mute


# pylint: disable=too-many-instance-attributes
class MongoHelper(object):

    # pylint: disable=too-many-arguments
    def __init__(self,
                 host='localhost',
                 port=37017,
                 db_name='sys_test_perf',
                 directory='/tmp',
                 prefix='data',
                 pause=0):
        self.port = port
        self.host = host
        self.db_name = db_name
        self.directory = directory
        self.prefix = prefix
        self.pause = pause

        self.mongo_uri = 'mongodb://' + self.host + ':' + str(self.port) + '/' + self.db_name

        self._points_collection = None
        self._mutes_collection = None

        self._mongo_client = None
        self._database = None

        self._tool = None
        self._temp_directory = None

    @property
    def mongo_client(self):
        """
        Get the mongo client instance.

        :return: MongoClient.
        """
        if self._mongo_client is None:
            self._mongo_client = MongoClient(self.mongo_uri)
        return self._mongo_client

    @property
    def temp_directory(self):
        """
        Get a temporary data directory.

        :return: str a temporary data directory.
        """
        if self._temp_directory is None:
            self._temp_directory = tempfile.mkdtemp(dir=self.directory, prefix=self.prefix)
        return self._temp_directory

    @property
    def tool(self):
        """
        Get the MLaunchTool instance.

        :return: MLaunchTool.
        """
        if self._tool is None:
            # Lazy load, only required if it is run.
            from mtools.mlaunch.mlaunch import MLaunchTool
            self._tool = MLaunchTool()
        return self._tool

    def _execute(self, *args):
        """
        Execute the command represented by args.

        :parameter list() args: The command arguments.
        """

        # When run in nosetests, sys.stdin may be closed and MLaunchTool will barf.
        old_stdin, sys.stdin = sys.stdin, StringIO()
        try:
            self.tool.run(' '.join([str(a) for a in args]))
        except:  # pylint: disable=bare-except
            LOG.warn("execute", args=args, exc_info=1)
        sys.stdin = old_stdin

    def drop(self):
        """ Drop the database. """
        try:
            self.mongo_client.drop_database(self.database)
        except:
            pass

    def start(self):
        """ Start a new mongo instance. Stop old instance first. """
        try:
            # connect directly to the port as we don't currently know the mlaunch directory.
            # set a short timeout so we don't pause for 30 seconds.
            mongo_client = MongoClient(
                self.mongo_uri, serverSelectionTimeoutMS=100, connectTimeoutMS=100)
            mongo_client.get_database('admin').command('shutdown', 1)
        except:  # pylint: disable=bare-except
            # pass
            LOG.warn('start', exc_info=1)

        self._execute('init', '--single', '--dir', self.temp_directory, '--port', self.port)
        if self.pause:
            sleep(self.pause)

    def stop(self):
        """ Stop any instance, remove any temp files. """
        self._execute('stop', '--port', self.port, '--dir', self.temp_directory)
        if self.pause:
            sleep(self.pause)
        try:
            shutil.rmtree(self.temp_directory)
        except:
            LOG.warn('stop rmtree failed', exc_info=1)

    @property
    def database(self):
        """
        Get the database.

        :return: The default database.
        """
        if self._database is None:
            self._database = self.mongo_client.get_database()
        return self._database


# pylint: disable=invalid-name
@unittest.skipUnless(enable_system_test(), 'Unit tests Only')
@attr('system-test')
class TestMuteExpired(unittest.TestCase):
    """ Test Mute expired against a real mongodb instance. """
    mongo = MongoHelper()
    """ A mongo helper instance. """

    @classmethod
    def setUpClass(cls):
        """ common code to all tests. """
        cls.mongo.start()

    def setUp(self):
        """ common code to setUp each test. """
        self.mongo.drop()

    @classmethod
    def tearDownClass(cls):
        """ common code cleanup for all tests. """
        cls.mongo.stop()

    def tearDown(self):
        """ common code to teardown each test. """
        self.mongo.drop()

    def _test(self):
        """ test fixture helper. """
        database = self.mongo.database

        points_collection = database['points']
        mutes_collection = database['mute_outliers']

        fixture, mute = load(SYS_FIXTURE_FILES, self.id(), points_collection, mutes_collection)
        expected = fixture.get('expected')
        result = mute_expired(mute, points_collection)
        if expected is None:
            self.assertIsNone(result)
        else:
            self.assertDictContainsSubset(expected, result)

    def test_just_mute(self):
        """ test only mute (shouldn't be possible). """
        self._test()

    def test_single(self):
        """ test one mute one point only. """
        self._test()

    def test_after_1(self):
        """ test Mute and Point, 1 newer points. """
        self._test()

    def test_after_10(self):
        """ test Mute and Point, 10 newer points. """
        self._test()

    def test_after_10_4_before_all_newer(self):
        """ test Mute and Point, 10 newer points and 4 older all rerun. """
        self._test()

    def test_after_10_4_older(self):
        """ test Mute and Point, 10 newer points and 4 older (no reruns). """
        self._test()

    def test_after_13(self):
        """ test Mute and Point, 13 newer points. """
        self._test()

    def test_after_14(self):
        """ test Mute and Point, 14 newer points. """
        self._test()

    def test_after_15(self):
        """ test Mute and Point, 15 newer points. """
        self._test()

    def test_before_4_all_newer(self):
        """ test Mute and Point, 4 before all rerun. """
        self._test()

    def test_before_4_all_older(self):
        """ test Mute and Point, 4 before no rerun. """
        self._test()

    def test_before_13_all_newer(self):
        """ test Mute and Point, 13 before all reruns. """
        self._test()

    def test_before_14_all_newer(self):
        """ test Mute and Point, 14 before all reruns. """
        self._test()

    def test_before_15_all_newer(self):
        """ test Mute and Point, 15 before all reruns. """
        self._test()

    def test_before_15_first_2_newer_3_older(self):
        """ test Mute and Point, 15 before, 3rd is not a rerun but the others are rerun. """
        self._test()

    def test_before_15_first_2_newer_mixed(self):
        """ test Mute and Point, 15 before, first 2 are reruns, the remainder are mixed. """
        self._test()
