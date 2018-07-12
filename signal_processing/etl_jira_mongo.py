#!/usr/bin/env python2.7
"""
Query sys-perf and performance BF tickets from Jira, and insert into a collection in MongoDB.

Drops collection if it exists.

Example:

etl_jira_mongo.py --jira-user USERNAME --jira-password PASSWORD --mongo-uri \
    'mongodb+srv://USERNAME:PASSWORD@performancedata-g6tsc.mongodb.net/perf?retryWrites=true' -d

If called from command line, main() is the entry point. In Lambda, we use zappa_handler() as
entry point. They are the same except for the fact that Zappa has already setup logging for us.
"""

import argparse
from collections import OrderedDict
import copy
from getpass import getpass
import logging
import os

import dateutil.parser
import jira
import pymongo

from bin.common import log

DB = 'perf'
COLLECTION = 'build_failures'
BATCH_SIZE = 1000
PROJECTS = [
    'performance', 'performance-4.0', 'performance-3.6', 'performance-3.4', 'performance-3.2',
    'performance-3.0', 'sys-perf', 'sys-perf-4.0', 'sys-perf-3.6', 'sys-perf-3.4', 'sys-perf-3.2'
]
JIRA_URL = 'https://jira.mongodb.org'

# Provide all options here. Use None when no default exists.
DEFAULT_OPTIONS = {
    'jira_user': None,
    'jira_password': None,
    'mongo_uri': 'mongodb://localhost:27017/' + DB,
    'projects': PROJECTS,
    'batch': BATCH_SIZE,
    'debug': False
}

# Dict to translate Jira field names we use in our mongodb collection into the internal Jira path.
FIELDS = OrderedDict([
    ('key', ('key', )),
    ('created', ('fields', 'created')),
    ('summary', ('fields', 'summary')),
    ('description', ('fields', 'description')),
    ('status', ('fields', 'status', 'name')),
    ('priority', ('fields', 'priority', 'name')),
    ('issuetype', ('fields', 'issuetype', 'name')),
    ('labels', ('labels', )),
    ('project', ('fields', 'customfield_14278')),
    ('buildvariants', ('fields', 'customfield_14277')),
    ('tasks', ('fields', 'customfield_12950')),
    ('tests', ('fields', 'customfield_15756')),
    ('first_failing_revision', ('fields', 'customfield_14851')),
    ('fix_revision', ('fields', 'customfield_14852')),
])

LOG = logging.getLogger(__name__)


class OptionError(Exception):
    """Exception raised for erroneous command line options."""
    pass


def lookup(issue, path):
    """
    Lookup a an attribute of an object.

    Ex: lookup(issue, (foo, bar)) returns issue.foo.bar

    We use both for jira issues as well as argparse args object.

    :param object issue: issue object returned by jira.issue().
    :param tuple path: Components of a path in a jira issue.
    :return: Value at path.
    """
    o = issue
    for p in path:
        try:
            o = getattr(o, p, None)
        except TypeError:
            if isinstance(p, int):
                o = o[p]
        if o is None:
            break
    return o


class EtlJira(object):
    def __init__(self, options):
        """
        Constructor merely stores args, they are used from self.jira and self.mongo properties.

        :param dict options: Options dictionary. See :const:`OPTIONS` above.
        """
        LOG.debug(options)
        self.options = options

        self._jira = None
        self._mongo = None
        self._db = None
        self._coll = None

    @property
    def jira(self):
        """
        Get the remote jira reference. Will prompt for username and password if not in self.options.

        This will clearly raise a JIRAError on 401/403.

        :return: a jira reference or throw an exception if there is an auth issue
        """
        if self._jira is None:
            LOG.debug("About to connect to jira.")
            if self.options['jira_user'] is None:
                self.options['jira_user'] = input("JIRA user id:")
            if self.options['jira_password'] is None:
                self.options['jira_password'] = getpass()
            self._jira = jira.JIRA(
                basic_auth=(self.options['jira_user'], self.options['jira_password']),
                options={
                    'server': JIRA_URL
                })
            # The following will fail on authentication error.
            # UPDATE: As of 2018-06-12 already the above contstructor now properly 403 fails on
            # on authentication error. Still leaving this here in case behavior changes again in the
            # future.
            self._jira.issue("PERF-1234")
        return self._jira

    @property
    def mongo(self):
        """
        Get the MongoClient instance.
        """
        if self._mongo is None:
            LOG.debug("Creating MongoClient instance.")
            self._mongo = pymongo.MongoClient(self.options['mongo_uri'])
        return self._mongo

    @property
    def db(self):
        """
        Get the db handle defined in mongo_uri.
        """
        if self._db is None:
            LOG.debug("Creating self.db handle.")
            self._db = self.mongo.get_database()
        return self._db

    @property
    def coll(self):
        """
        Get the build_failures collection.
        """
        if self._coll is None:
            LOG.debug("Creating self.coll handle.")
            self._coll = self.db.get_collection(COLLECTION)
        return self._coll

    def query_bfs(self):
        """
        Return a list of BF issues.
        """
        jql = 'project = BF AND "Evergreen Project" in (' + ", ".join(
            self.options['projects']) + ') order by KEY DESC'
        # maxResults default is 50.
        # At the time of writing this, query returned 544 BF issues. (After 4 years in operation.)
        # main() would need a loop to be able to handle paginated result sets.
        issues = self.jira.search_issues(jql, maxResults=-1)
        LOG.debug("Jira found %d issues.", len(issues))
        return issues

    def drop_collection(self):
        """
        Drop the build_failures collection.
        """
        self.coll.drop()

    def create_indexes(self):
        """
        Create the indexes needed on build_failures collection.
        """
        # TODO: Discussion in PERF-1528 envisioned some centralized yaml file to define these

        # MongoDB restriction: Can only have one array field per index. Unfortunately these
        # are all arrays...
        # Intentionally leaving "project" unindexed. It's low cardinality and redundant with
        # both variants and tasks.
        self.coll.create_index([('buildvariants', pymongo.ASCENDING)])
        self.coll.create_index([('tasks', pymongo.ASCENDING)])
        self.coll.create_index([('first_failing_revision', pymongo.ASCENDING)])
        self.coll.create_index([('fix_revision', pymongo.ASCENDING)])
        # In addition, note that 'key' field is copied into '_id'

    def insert_bf_in_mongo(self, issues):
        """
        Insert issues into build_failures collection.

        :param list issues: List of jira issue objects
        """
        docs = []
        for issue in issues:
            doc = OrderedDict()
            docs.append(doc)
            for field in FIELDS:
                value = lookup(issue, FIELDS[field])
                if value is not None:
                    doc[field] = value
            if 'created' in doc:
                doc['created'] = dateutil.parser.parse(doc['created'])
            doc['_id'] = doc['key']
            if len(docs) > self.options['batch']:
                self.coll.insert(docs)
                docs = []
        LOG.info("Inserting %d issues.", len(docs))
        if docs:
            self.coll.insert(docs)

    def save_bf_in_mongo(self, issues):
        """
        Save list of issues in MongoDB.

        :param list issues: List of jira issue objects
        """
        self.drop_collection()
        self.create_indexes()
        self.insert_bf_in_mongo(issues)

    def run(self):
        """
        The method that runs everything: query BFs, then save them in MongoDB.
        """
        issues = self.query_bfs()
        self.save_bf_in_mongo(issues)


def parse_command_line():
    """
    Parse the command line options
    """
    parser = argparse.ArgumentParser(
        description='Copy perf BF tickets from Jira to MongoDB.',
        epilog='You will be prompted for --jira-user and --jira-password if not provided.')
    parser.add_argument('-u', '--jira-user', help='Your Jira username')
    parser.add_argument('-p', '--jira-password', help='Your Jira password')
    parser.add_argument('--mongo-uri', help='MongoDB connection string.')
    parser.add_argument('--projects', help='the Projects', nargs='+')
    parser.add_argument('--batch', help='The insert batch size', type=int)
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()

    return args


def parse_options():
    """
    Get options from 1) command line, 2) environment, 3) DEFAULT_OPTIONS
    """
    options = copy.copy(DEFAULT_OPTIONS)

    args = parse_command_line()

    for key in options:
        arg = lookup(args, (key, ))
        if arg:
            options[key] = arg
        elif key.upper() in os.environ:
            options[key] = os.environ[key.upper()]

    return options


def zappa_handler(event, context):
    """
    When deployed with Zappa, this is the entry point.

    Like main(), but without setup_logging(). Zappa manages logging, including whether to log DEBUG
    or not.
    """
    options = parse_options()
    EtlJira(options).run()


def main():
    """
    Main function.
    """
    options = parse_options()
    log.setup_logging(options['debug'])
    EtlJira(options).run()


if __name__ == '__main__':
    main()
