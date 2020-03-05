"""
DSI's interaction with Cedar (aka "Curator" aka "Expanded Metrics")
"""

import logging
import os

import json
from datetime import datetime
import pytz
import requests

LOG = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class Report(object):
    """
    Report is the top level object to represent a suite of performance tests
    and is used to feed data to a cedar instance. All of the test data is in
    the "tests" field, with additional metadata common to all tests in the
    top-level fields of the Report structure.
    """
    def __init__(self, runtime=None):
        """
        :param runtime dict
        has the following keys:
          project: Name of the Evergreen project.
          version: Version id from Evergreen.
          order: Evergreen order based on git commit.
          variant: Build variant task ran on.
          task_name: Name of task.
          task_id: Unique id for this task run.
          execution_number: The execution (run) of this specific `task_id`.
        """
        if runtime is None:
            runtime = {}
        self.project = runtime.get('project')
        self.version = runtime.get('version_id')
        self.variant = runtime.get('build_variant')
        self.task_name = runtime.get('task_name')
        self.task_id = runtime.get('task_id')
        self.execution_number = runtime.get('execution')
        self.mainline = not runtime.get('is_patch', True)

        try:
            self.order = int(runtime.get('order'))
        except (ValueError, TypeError):
            self.order = None

        self.tests = []
        self.bucket = BucketConfiguration()

    def add_test(self, test):
        """
        Add a completed test.
        :param test CedarTest test to add
        """
        self.tests.append(test)

    def write_report(self):
        """
        Write to cedar_report.json
        """
        with open('cedar_report.json', 'w') as out:
            out.write(self.as_json())

    def as_json(self):
        """
        :return: json representation of this entity
        """
        return json.dumps(self.as_dict(), indent=4)

    def as_dict(self):
        """
        :return: dictionary representation of this entity. Recursively dict types.
        """
        return {
            'project': self.project,
            'version': self.version,
            'order': self.order,
            'variant': self.variant,
            'task_name': self.task_name,
            'task_id': self.task_id,
            'execution_number': self.execution_number,
            'mainline': self.mainline,
            'tests': sorted([test.as_dict() for test in self.tests], key=lambda d: d['created_at']),
            'bucket': self.bucket.as_dict(),
        }


class CedarTest(object):
    """
    CedarTest holds data about a specific test and its subtests. You should not
    populate the ID field, and instead populate the entire Info structure. ID
    fields are populated by the server by hashing the Info document along with
    high level metadata that is, in this representation, stored in the report
    structure.
    """
    def __init__(self, name, created, completed):
        """
        :param str name: Name of the test.
        :param float created: Time in seconds from the epoch to when the test
        began (timestamp).
        :param float completed: Time in seconds from the epoch to when the test
        ended (timestamp).
        """
        self._raw_params = {'name': name, 'created': created, 'completed': completed}
        self._created_at = datetime.fromtimestamp(created,
                                                  tz=pytz.UTC).replace(tzinfo=pytz.UTC).isoformat()
        self._completed_at = datetime.fromtimestamp(
            completed, tz=pytz.UTC).replace(tzinfo=pytz.UTC).isoformat()

        self.info = TestInfo(name)
        self.metrics = []
        self.sub_tests = []

    def clone(self):
        """Clone this CedarTest object without metrics or sub-tests"""
        return CedarTest(**self._raw_params)

    def add_metric(self, name, rollup_type, value, user_submitted=False):
        """
        Add a "rollup" (calculated) metric to a test. This must be of the
        predefined types specifed above.

        For the parameters see `TestMetric.__init__`.
        """
        metric = TestMetric(name=name,
                            rollup_type=rollup_type,
                            value=value,
                            user_submitted=user_submitted)
        self.metrics.append(metric)

    def add_tag(self, tag):
        """
        Convenience function to add a tag to `info`.

        :param str tag: The tag to append.
        """
        self.info.tags.add(tag)

    def set_thread_level(self, thread_level):
        """
        Convenience function to add the thread level to `info.args`.

        :param int thread_level: The thread level to set.
        """
        self.set_argument('thread_level', thread_level)

    def set_argument(self, argument, value):
        """
        Convenience function to set an argument to `info.args`.

        :param str argument: The argument name (key).
        :param int value: The argument value.
        """
        self.info.args[argument] = value

    def as_dict(self):
        """
        :return: dictionary representation of this entity. Recursively dict types.
        """
        return {
            'info':
                self.info.as_dict(),
            'created_at':
                self._created_at,
            'completed_at':
                self._completed_at,
            'artifacts': [],  # use TestArtifact below when we support it
            'metrics':
                sorted([metric.as_dict() for metric in self.metrics], key=lambda d: d['name']),
            'sub_tests':
                sorted([test.as_dict() for test in self.sub_tests],
                       key=lambda d: d['test_name'] + str(d['trial'])),
        }


# pylint: disable=too-few-public-methods
class TestInfo(object):
    """
    TestInfo holds metadata about the test configuration and execution. The
    parent field holds the content of the ID field of the parent test for sub
    tests, and should be populated automatically by the client when uploading
    results.
    """
    def __init__(self, name, trial=0):
        """
        :param str name: Name of the test.
        :param int trial: Run of this specific test. Defaults to 0.
        """
        self.test_name = name
        self.trial = trial
        self.tags = set()
        self.args = {}

    def as_dict(self):
        """
        :return: dictionary representation of this entity. Recursively dict types.
        """
        return {
            'test_name': self.test_name,
            'trial': self.trial,
            'tags': sorted(list(self.tags)),
            'args': self.args,
        }


# pylint: disable=too-few-public-methods
class TestMetric(object):
    """
    TestMetrics is a structure that holds computed metrics for an entire test
    in the case that test harnesses need or want to report their own test
    outcomes.
    """
    def __init__(self, name, rollup_type, value, user_submitted=False):
        """
        :param str name: Name of the metric.
        :param str rollup_type: Type of the rolled up metric.
        :param value: Value of the metric.
        :type value: int, float.
        :param bool user_submitted: Whether this metric was submitted by a
        user or not. Defaults to `False`.
        """
        self.name = name
        self.type = rollup_type
        self.value = value
        self.user_submitted = user_submitted

    def as_dict(self):
        """
        :return: dictionary representation of this entity. Recursively dict types.
        """
        return {
            'name': self.name,
            'type': self.type,
            'value': self.value,
            'user_submitted': self.user_submitted,
        }


# pylint: disable=too-few-public-methods
class BucketConfiguration(object):
    """
    BucketConfiguration describes the configuration information for an AWS s3
    bucket for uploading test artifacts for this report.
    """
    def __init__(self):
        self.api_key = ''
        self.api_secret = ''
        self.api_token = ''
        self.region = ''
        self.name = ''
        self.prefix = ''

    def as_dict(self):
        """
        :return: dictionary representation of this entity. Recursively dict types.
        """
        return {
            'api_key': self.api_key,
            'api_secret': self.api_secret,
            'api_token': self.api_token,
            'region': self.region,
            'name': self.name,
            'prefix': self.prefix,
        }


# Artifacts not currently supported
#
# class TestArtifact(object):
#     """
#     TestArtifact is an optional structure to allow you to upload and attach
#     metadata to results files.
#     """
#
#     def __init__(self):
#         self.bucket = ''
#         self.path = ''
#         self.tags = []
#         # where does created come from???
#         self._created_at = datetime.fromtimestamp(created).replace(tzinfo=pytz.UTC).isoformat()
#         self.local_path = ''
#         self.is_ftdc = False
#         self.s_bson = False
#         self.is_uncompressed = False
#         self.is_gzip = False
#         self.is_tarball = False
#         self.events_raw = False
#         self.events_histogram = False
#         self.events_interval_summary = False
#         self.events_collapsed = False
#         self.convert_gzip = False
#         self.convert_bson_to_ftdc = False
#         self.convert_json_to_ftdc = False
#         self.convert_csv_to_ftdc = False
#
#     def as_dict(self):
#         return {
#             'bucket': self.bucket,
#             'path': self.path,
#             'tags': self.tags,
#             'created_at': self._created_at,
#             'local_path': self.local_path,
#             'is_ftdc': self.is_ftdc,
#             's_bson': self.s_bson,
#             'is_uncompressed': self.is_uncompressed,
#             'is_gzip': self.is_gzip,
#             'is_tarball': self.is_tarball,
#             'events_raw': self.events_raw,
#             'events_histogram': self.events_histogram,
#             'events_interval_summary': self.events_interval_summary,
#             'events_collapsed': self.events_collapsed,
#             'convert_gzip': self.convert_gzip,
#             'convert_bson_to_ftdc': self.convert_bson_to_ftdc,
#             'convert_json_to_ftdc': self.convert_json_to_ftdc,
#             'convert_csv_to_ftdc': self.convert_csv_to_ftdc,
#         }


def _create_curator_runner(value, host, config):
    """
    Nop curator invocations if config['runtime_secret']['perf_jira_user'] not defined.

    :param value: when called from run_curator: X this will be X. For now only support 'normal'
    :param host: the host.py host to run on
    :param config: top-level config-dict. used for runtime_secret to get ldap config
    :return: CuratorRunner
    """
    if value != 'normal':
        raise NotImplementedError('Curator of type ' + value + ' not supported')
    if 'runtime_secret' in config and 'perf_jira_user' in config['runtime_secret']:
        return ShellCuratorRunner(value, host, config)
    return NopCuratorRunner(value, host, config)


class CertRetriever(object):
    """Retrieves certs/keys from the cedar API."""
    def __init__(self, config):
        """
        :param config: top-level ConfigDict
        """
        self.config = config
        self.auth = json.dumps({
            'username': self.config['runtime_secret']['perf_jira_user'],
            'password': self.config['runtime_secret']['perf_jira_pw']
        })

    @staticmethod
    def _fetch(url, output, **kwargs):
        """
        Fetch a url to a file if the file doesn't already exist.

        :param url: url to fetch and write to `output`
        :param output: file name to write the url contents to
        :param kwargs: passed along to `request.get`. Example is `data="foo"`
        :return: `output` for convenience
        """
        if os.path.exists(output):
            return output
        resp = requests.get(url, **kwargs)
        resp.raise_for_status()
        with open(output, 'w') as pem:
            pem.write(resp.text)
        return output

    def root_ca(self):
        """
        :return: the root cert authority pem file from cedar
        """
        return self._fetch('https://cedar.mongodb.com/rest/v1/admin/ca', 'cedar.ca.pem')

    def user_cert(self):
        """
        :return: the user-level pem
        """
        return self._fetch('https://cedar.mongodb.com/rest/v1/admin/users/certificate',
                           'cedar.user.crt',
                           data=self.auth)

    def user_key(self):
        """
        :return: the user-level key
        """
        return self._fetch('https://cedar.mongodb.com/rest/v1/admin/users/certificate/key',
                           'cedar.user.key',
                           data=self.auth)


# pylint: disable=too-few-public-methods
class CuratorRunner(object):
    """Runs curator via a host.py host"""
    def __init__(self, value, host, config):
        """
        :param value: the run_curator type
        :param host: host.py host
        :param config: top-level config-dict
        """
        self.value = value
        self.host = host
        self.config = config

    def run_curator(self):
        """
        Do your magic.
        :return: output from host.run_command(the-generated-command)
        """
        raise NotImplementedError('Must be implemented in subclasses')


# pylint: disable=too-few-public-methods
class NopCuratorRunner(CuratorRunner):
    """Does nothing. Used when no runtime_secret in config (e..g when running DSI locally)"""
    def run_curator(self):
        pass


# pylint: disable=too-few-public-methods
class ShellCuratorRunner(CuratorRunner):
    """Runs curator for realsies."""
    def __init__(self, value, host, config, retriever=None):
        """
        :param value: the run_curator type
        :param host: host.py host
        :param config: top-level config-dict
        :param retriever: CertRetriever to use. Will construct one from given config if None
        """
        super(ShellCuratorRunner, self).__init__(value, host, config)
        self.retriever = retriever if retriever is not None else CertRetriever(config)

    def run_curator(self):
        """
        Do your magic.
        :return: output from host.run_command(the-generated-command)
        """
        # allow ${bootstrap.curator} if running DSI locally
        curator = self.config['bootstrap']['curator'] if 'bootstrap' in self.config \
            and 'curator' in self.config['bootstrap'] else './curator'

        command = [
            curator,
            'poplar',
            'send',
            '--service',
            'cedar.mongodb.com:7070',
            '--cert',
            self.retriever.user_cert(),
            '--key',
            self.retriever.user_key(),
            '--ca',
            self.retriever.root_ca(),
            '--path',
            'cedar_report.json',
        ]
        return self.host.run(command)


def run_curator(value, host, config):
    """
    Entry-point from test_control. See command_runner.py
    :param value the type of curator run. For now always 'normal' but additional
    values may be added in the future
    :param host the host.py host on which to run the curator and associated shell invocations
    :param config the top-level ConfigDict
    """
    runner = _create_curator_runner(value, host, config)
    return runner.run_curator()
