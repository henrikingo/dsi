#!/usr/bin/env python2.7
"""
Query sys-perf and performance BF tickets from Jira, and insert into a collection in MongoDB.

Drops collection if it exists.

Example:

etl_jira_mongo.py --jira-user USERNAME --jira-password PASSWORD --mongo-uri \
    'mongodb+srv://USERNAME:PASSWORD@performancedata-g6tsc.mongodb.net/perf?retryWrites=true' -d

If called from command line, main() is the entry point.
"""
# pylint: disable=redefined-builtin
from builtins import input  # input does an eval on 2.7

import ast
from collections import OrderedDict
from getpass import getpass
import structlog

import click
import dateutil.parser
import jira
import pymongo

from bin.common import log
from signal_processing.keyring.credentials import Credentials

DB = 'perf'
COLLECTION = 'build_failures'
DEFAULT_BATCH_SIZE = 1000
DEFAULT_PROJECTS = ('performance', 'performance-4.0', 'performance-3.6', 'performance-3.4',
                    'performance-3.2', 'performance-3.0', 'sys-perf', 'sys-perf-4.0',
                    'sys-perf-3.6', 'sys-perf-3.4', 'sys-perf-3.2')
DEFAULT_MONGO_URI = 'mongodb://localhost:27017/' + DB
JIRA_URL = 'https://jira.mongodb.org'

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

MANDATORY_ARRAY_FIELDS = ('project', 'first_failing_revision', 'fix_revision')

LOG = structlog.getLogger(__name__)


class OptionError(Exception):
    """Exception raised for erroneous command line options."""
    pass


def lookup(issue, path):
    """
    Lookup an attribute of an object.

    Ex: lookup(issue, (foo, bar)) returns issue.foo.bar

    We use both for jira issues as well as argparse args object.

    :param object issue: issue object returned by jira.issue().
    :param tuple path: Components of a path in a jira issue.
    :return: Value at path.
    """
    lookup_object = issue
    for component in path:
        try:
            lookup_object = getattr(lookup_object, component, None)
        except TypeError:
            if isinstance(component, int):
                lookup_object = lookup_object[component]
        if lookup_object is None:
            break
    return lookup_object


class JiraCredentials(object):
    """Jira basic authentication credentials."""

    # pylint: disable=too-few-public-methods

    def __init__(self, username, password):
        """Create a JiraCredentials from a username and password."""
        self.username = username
        self.password = password

    def __eq__(self, other):
        if type(other) is type(self):
            return other.username == self.username and other.password == self.password
        return False

    def __str__(self):
        return '({}, {})'.format(self.username, self._redact_password(self.password))

    @staticmethod
    def _redact_password(password):
        """
        Redact the password.

        :param password: The password to redact.
        :type password: str or None.
        :return: A redacted password.
        """

        if password is not None:
            return '*' * min(8, max(8, len(password)))
        return password

    def encode(self):
        """
        Encode the Jira credentials.

        :return: A string of encoded credentials.
        """
        return '{}'.format([self.username, self.password])

    @staticmethod
    def decode(credentials):
        """
        Decode the Jira credentials

        :param str credentials: The encoded Jira credentials.
        :return: A JiraCredentials instance.
        """
        if credentials is not None:
            username, password = ast.literal_eval(credentials)
            return JiraCredentials(username, password)
        return JiraCredentials(None, None)


def new_jira_client(jira_user=None, jira_password=None):
    """
    Create a new Jira client.

    Will prompt for username and password if not specified.
    This will clearly raise a JIRAError on 401/403.

    :return: a tuple with the Jira client and the credentials that were used or throw
        an exception if there is an authentication issue.
    """
    LOG.debug('Initializing a new Jira client.')
    if jira_user is None:
        jira_user = input('JIRA user id: ')
    if jira_password is None:
        jira_password = getpass()
    jira_client = jira.JIRA(
        basic_auth=(jira_user, jira_password), options={'server': JIRA_URL}, max_retries=1)
    # The following will fail on authentication error.
    # UPDATE: As of 2018-06-12 already the above constructor now properly 403 fails on
    # on authentication error. Still leaving this here in case behavior changes again in the
    # future.
    LOG.debug("About to connect to jira.")
    jira_client.issue('PERF-1234')
    return jira_client, Credentials(jira_user, jira_password)


class EtlJira(object):
    """
    Class to load BF tickets from JIRA into database.
    """

    def __init__(self, jira_client, mongo_client, projects, batch_size):
        """
        Constructor merely stores args.

        :param jira.Jira jira_client: A Jira client..
        :param mongo.MongoClient mongo_client: A Mongo client.
        :param tuple(str) projects: A tuple containing the Evergreen projects to process.
        :param int batch_size: The insert batch size.
        """
        LOG.debug('Create EtlJira')

        self._jira = jira_client
        self._build_failures = mongo_client.get_database().get_collection(COLLECTION)

        self._projects = projects
        self._batch_size = batch_size

    def query_bfs(self):
        """
        Return a list of BF issues.
        """
        jql = 'project = BF AND "Evergreen Project" in (' + ", ".join(
            self._projects) + ') order by KEY DESC'
        # maxResults default is 50.
        # At the time of writing this, query returned 544 BF issues. (After 4 years in operation.)
        # main() would need a loop to be able to handle paginated result sets.
        issues = self._jira.search_issues(jql, maxResults=-1)
        LOG.debug("Jira found issues.", issues=issues)
        return issues

    def drop_collection(self):
        """
        Drop the build_failures collection.
        """
        self._build_failures.drop()

    def create_indexes(self):
        """
        Create the indexes needed on build_failures collection.
        """
        # TODO: Discussion in PERF-1528 envisioned some centralized yaml file to define these

        # MongoDB restriction: Can only have one array field per index. Unfortunately these
        # are all arrays...
        # Intentionally leaving "project" unindexed. It's low cardinality and redundant with
        # both variants and tasks.
        self._build_failures.create_index([('buildvariants', pymongo.ASCENDING)])
        self._build_failures.create_index([('tasks', pymongo.ASCENDING)])
        self._build_failures.create_index([('first_failing_revision', pymongo.ASCENDING)])
        self._build_failures.create_index([('fix_revision', pymongo.ASCENDING)])
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
            for field in MANDATORY_ARRAY_FIELDS:
                if field not in doc:
                    doc[field] = []
            if len(docs) > self._batch_size:
                self._build_failures.insert(docs)
                docs = []
        LOG.info("Inserting issues.", count=len(docs))
        if docs:
            self._build_failures.insert(docs)

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
        LOG.info("etl_jira_mongo completed successfully", num_issues=len(issues))


@click.command()
@click.option('-u', '--jira-user', help='Your Jira username')
@click.option('-p', '--jira-password', help='Your Jira password')
@click.option('--mongo-uri', default=DEFAULT_MONGO_URI, help='MongoDB connection string')
@click.option(
    '--project',
    'projects',
    type=str,
    default=DEFAULT_PROJECTS,
    multiple=True,
    help='An Evergreen project to load. Can be specified multiple times to include '
    'several projects. Defaults to {}'.format(DEFAULT_PROJECTS))
@click.option('--batch', type=int, default=DEFAULT_BATCH_SIZE, help='The insert batch size')
@click.option('-d', '--debug', is_flag=True, default=False, help='Enable debug output')
def main(jira_user, jira_password, mongo_uri, projects, batch, debug):
    # pylint: disable=too-many-arguments
    """
    Copy perf BF tickets from Jira to MongoDB.

    You will be prompted for --jira-user and --jira-password if not provided.
    """
    try:
        log.setup_logging(debug)
        jira_client, _ = new_jira_client(jira_user, jira_password)
        mongo_client = pymongo.MongoClient(mongo_uri)
        EtlJira(jira_client, mongo_client, projects, batch).run()
    except:  # pylint: disable=bare-except
        LOG.error('Unexpected Exception loading JIRA project data.', exc_info=1)
