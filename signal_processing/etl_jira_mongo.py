#!/usr/bin/env python2.7

import argparse
from collections import OrderedDict
from getpass import getpass
import logging

import dateutil.parser
import jira
from pymongo import MongoClient

DB = "evgdw"
BATCH_SIZE = 1000
PROJECTS = ["performance", "sys-perf"]
JIRA_URL = 'https://jira.mongodb.org'
FIELDS = OrderedDict([
    ('key', ('key', )),
    ('created', ('fields', 'created')),
    ('summary', ('fields', 'summary')),
    ('description', ('fields', 'description')),
    ('status', ('fields', 'status', 'name')),
    ('priority', ('fields', 'priority', 'name')),
    ('issuetype', ('fields', 'issuetype', 'name')),
    ('first_failing_revision', ('fields', 'customfield_14851')),
    ('fix_revision', ('fields', 'customfield_14852')),
    ('buildvariants', ('fields', 'customfield_14277')),
    ('tasks', ('fields', 'customfield_12950')),
    ('tests', ('fields', 'customfield_15756')),
    ('project', ('fields', 'customfield_14278')),
    ('evergreen project', ('fields', 'customfield_14278')),
    ('labels', ('labels', )),
])

logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger(__name__)


class OptionError(Exception):
    """Exception raised for erroneous command line options."""
    pass


class EtlJira(object):
    def __init__(self, args):
        self.args = args
        if not self.args.jira_user:
            self.args.jira_user = input("JIRA user id:")
        if not self.args.jira_password:
            self.args.jira_password = getpass()

        LOGGER.debug("About to connect to jira")
        self._jira = None
        self.mongo = MongoClient(self.args.mongo_uri)
        # Get the database defined in mongo_uri
        self.db = self.mongo.get_database()

    @property
    def jira(self):
        """
        get the remote jira reference
        This will clearly raise a JIRAError on 401.

        :return: a jira reference or throw an exception if there is an auth issue
        """
        if self._jira is None:
            LOGGER.debug("About to connect to jira")
            self._jira = jira.JIRA(
                basic_auth=(self.args.jira_user, self.args.jira_password),
                options={
                    'server': JIRA_URL
                })
            # the following will fail on authentication error.
            self._jira.issue("PERF-1103")
        return self._jira

    @staticmethod
    def lookup(issue, path):
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

    def query_bf_with_githash(self):
        jql = 'project = BF AND "Evergreen Project" in (' + ", ".join(
            self.args.projects
        ) + ') AND "First Failing Revision (git hash)" is not EMPTY order by KEY DESC'
        return self.jira.search_issues(jql, maxResults=1000)

    def save_bf_in_mongo(self, issues):
        docs = []
        for issue in issues:
            doc = OrderedDict()
            docs.append(doc)
            print(issue)
            for key in FIELDS:
                doc[key] = EtlJira.lookup(issue, FIELDS[key])
            if 'created' in doc:
                doc['created'] = dateutil.parser.parse(doc['created'])
            if len(docs) > self.args.batch:
                self.db.build_failures.insert(docs)
                docs = []
        if docs:
            self.db.build_failures.insert(docs)


def parse_command_line():
    '''
    Parse the command line options
    '''
    parser = argparse.ArgumentParser(description='Specify one Evergreen and one MongoDB please.')
    parser.add_argument('-u', '--jira-user', help='Your Jira username (Required)')
    parser.add_argument('-p', '--jira-password', help='Your Jira password (Required)')
    parser.add_argument(
        '--mongo-uri',
        default='mongodb://localhost:27017/' + DB,
        help='MongoDB connection string. (A MongoDB is required!)')
    parser.add_argument('--projects', default=PROJECTS, help='the Projects', nargs='+')
    parser.add_argument('--batch', default=BATCH_SIZE, help='The insert batch size', type=int)
    args = parser.parse_args()

    return args


def main():
    args = parse_command_line()
    etl = EtlJira(args)
    issues = etl.query_bf_with_githash()
    etl.save_bf_in_mongo(issues)


if __name__ == '__main__':
    main()
