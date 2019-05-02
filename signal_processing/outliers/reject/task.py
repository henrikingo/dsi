"""
Automatic handling of outlier results.

A test is classed as an automatic failure and rejected iff:
 * it is not part of a patch run.
 * it is part of the latest revision (see the subsequent sections for the definition of latest).
 * there are no correctness issues.
 * >= 15 data point available from the previous change point.
 * the task is not muted.
 * the consecutive failure limit not reach (3 consecutive cumulative failures).

An *outlier* is a data point which has been explicitly flagged by the GESD
algorithm. Generally this means that the z-score is more than 3 sigmas from the mean. We can be
confident that these data points are *real* outliers.

A *suspicious outlier* is a data point that was considered by the GESD algorithm. The number
of suspicious data points is an input to the algorithm. Generally suspicious outliers are *not
real* outliers.

A result is deemed to be the *latest* if the order is greater than or equal to the last order value
in the perf.points collection for the test_identifier.

A point is deemed rejected if it was a *confirmed outlier* when it was run and the it was the
latest task at that point in time. So by definition, rerunning an old task where there is newer
data available will never result in this data being rejected.

When a task is run or rerun, if it is an outlier and it is the latest task,
then a field called rejected is set to True otherwise the rejected field is not set.

When a task is not the latest, the state of the rejected field remains unchanged.

So, rejected implies that this task was an outlier when it was first run.

When you look at the state of a point, the value of the rejected field and the state of the outlier
field determine whether a point was initially rejected and that it is still an outlier.

When the outlier field is not None then this point is an outlier.

When rejected is True and outlier is not None then the point is an outlier and it was
automatically rejected. Data points of this type should not be displayed.

When rejected is True and outlier is None then the point is no longer a confirmed outlier but it
was initially automatically rejected. Data points of this type should be displayed.

When rejected is False (or None) and outlier is not None then the point is an outlier but
it was not automatically rejected. Data points of this type should be displayed.

When rejected is False (None) and outlier is None then the point is not an outlier and it was not
automatically rejected. Data points of this type should be displayed.
"""
from __future__ import print_function

import json

import pymongo
import structlog
from bson import Regex
from nose.tools import nottest

from signal_processing.commands.helpers import WHITELISTED_OUTLIER_TASKS, MUTE_OUTLIERS
from signal_processing.model.configuration import ConfigurationModel, combine_outlier_configs
from signal_processing.model.points import PointsModel
from signal_processing.outliers.list_mutes import mute_expired

STATUS_PASS = 'pass'
"""
A test has passed.
"""

STATUS_FAIL = 'fail'
"""
A test has failed.
"""

LOG = structlog.getLogger(__name__)


def get_json(filename):
    """ Load a file and parse it as json """
    with open(filename) as json_file:
        return json.load(json_file)


class TaskAutoRejector(object):
    """
    A class to apply the rules for automatic outlier detection for a task (a group of tests).

    A test is classed as automatic failures iff:
     * it is not part of a patch run.
     * it is part of the latest revision (run by evergreen).
     * there are no correctness issues.
     * >= 15 data point available from the previous change point.
     * the task is not muted.
     * the consecutive failure limit not reach (3 consecutive cumulative failures).
    """

    # pylint: disable=too-few-public-methods,too-many-arguments, too-many-instance-attributes
    def __init__(self, results, project, variant, task, perf_json, mongo_uri, patch, status,
                 override_config):
        """
        :param list(dict) results: The outlier test results for this task.
        :param str project: The project name for this task.
        :param str variant: The variant for this task.
        :param str task: The task name for this task.
        :param dict perf_json: The performance data for this task.
        :param str mongo_uri: The uri to connect to the cluster.
        :param bool patch: True if this is a patch.
        :param dict status: The task status.
        :param dict override_config: The override_config from the user.
        """
        self.results = [TestAutoRejector(result, self, override_config) for result in results]

        self.override_config = override_config
        self.project = project
        self.variant = variant
        self.task = task
        self.task_identifier = {'project': self.project, 'variant': self.variant, 'task': self.task}

        self.revision = perf_json['revision']
        self.order = perf_json['order']

        self.mongo_uri = mongo_uri
        self.patch = patch
        self.status = status

        self._whitelisted = None

        self._points_model = None
        self._configuration_model = None

        self._correct = None
        self._failed_correctness_reports = None

        self._rejects = None
        self._config = None
        self._canary_pattern = None
        self._correctness_pattern = None

    @property
    def points_model(self):
        """
        Get a reference to the PointsModel Object.
        :return: The PointsModel instance (lazy evaluated).
        :rtype: detect_changes.PointsModel
        """
        if self._points_model is None:
            self._points_model = PointsModel(self.mongo_uri)
        return self._points_model

    @property
    def configuration_model(self):
        """
        Get a reference to the ConfigurationModel Object.
        :return: The PointsModel instance (lazy evaluated).
        :rtype: detect_changes.PointsModel
        """
        if self._configuration_model is None:
            self._configuration_model = ConfigurationModel(self.mongo_uri)
        return self._configuration_model

    @property
    def config(self):
        if self._config is None:
            configurations = self.configuration_model.get_configuration(self.task_identifier)
            self._config = combine_outlier_configs(self.task_identifier, configurations,
                                                   self.override_config)
        return self._config

    @property
    def correct(self):
        """
        Ensure this task is correct, that is no correctness tests have failed.
        :return: True if no correctness test failed.
        """
        if self._correct is None:
            if self.status is None:
                LOG.warn('correct: status is None assuming correct is False!')
                self._correct = False
            else:
                if self.status['failures'] > 0:
                    LOG.debug('correct', pattern=self.correctness_pattern.pattern)
                    all_tests = self.status['results']
                    self._failed_correctness_reports = [
                        result['test_file'] for result in all_tests
                        if self.correctness_pattern.match(result['test_file'])
                        and result['status'] == STATUS_FAIL
                    ]
                    self._correct = len(self._failed_correctness_reports) == 0
                else:
                    self._correct = True
        LOG.debug('correctness', correct=self._correct, failed=self._failed_correctness_reports)
        return self._correct

    @property
    def rejects(self):
        """
        Get the list of all rejected tests.

        The following updates are applied in a single transaction:
            * All points in the order range which are not confirmed outliers will have the
            'results.$.outlier' field set to False.
            * All outliers will have the 'results.$.outlier' field set to True.
            * If the latest order is a confirmed outlier then 'results.$.reject' field is set to
            True.

        The extra factors to bear in mind:
            # A point is an outlier and rejected if it is a outlier when it was
            run *OR* rerun as the latest task. These point should not be displayed.
            # A point is not an outlier and is rejected if it was initially rejected (when first run
            or rerun) rerun but it is no longer a confirmed outlier. These point should be
            displayed.
            # A point is an outlier and is not rejects if it is an outlier and it was not
            an outlier when initially run. These point should not be displayed.
            # A point is not an outlier and is not rejects if it is not a confirmed outlier and it
            was not an outlier when initially run.

        If the task is whitelisted then no rejects are returned.
        Point that are outliers or rejects should not be displayed.

        :param TaskAutoRejector auto_rejector: The auto rejector instance.
        :return: The pymongo update operations and rejects tests.
        :rtype: (list(pymongo.Update), list(TestAutoRejector)).
        """
        if self._rejects is None:
            rejects = []
            for result in self.results:
                if result.latest and result.outlier_orders and self.order in result.outlier_orders:
                    rejects.append(result)
            self._rejects = rejects
        LOG.info('rejects list', rejects=self._rejects)
        return self._rejects

    def filtered_rejects(self):
        """
        filter rejects based on a set of rules.

        :returns: A list of the rejected test names.

        """
        LOG.debug('filtered rejects list', patch=self.patch, correct=self.correct)
        rejects = [
            result for result in self.rejects
            if not self.patch and self.correct and result.reject(self.order)
        ]
        LOG.debug('filtered rejects list', rejects=rejects)
        return rejects

    @property
    def canary_pattern(self):
        """
        Get the canary pattern. If this comes from the configuration collection then it is a
        bson.Regex and needs to be translated.
        :return: The canary task.
        """
        if self._canary_pattern is None:
            canary_pattern = self.config.canary_pattern
            if isinstance(canary_pattern, Regex):
                canary_pattern = canary_pattern.try_compile()
            self._canary_pattern = canary_pattern
        return self._canary_pattern

    @property
    def correctness_pattern(self):
        """
        Get the correctness pattern. If this comes from the configuration collection then it is a
        bson.Regex and needs to be translated
        :return: The correctness task.
        """
        if self._correctness_pattern is None:
            correctness_pattern = self.config.correctness_pattern
            if isinstance(correctness_pattern, Regex):
                correctness_pattern = correctness_pattern.try_compile()
            self._correctness_pattern = correctness_pattern
        return self._correctness_pattern

    def canary(self, test):
        """
        Check if this test is a canary.
        :param TestAutoRejector test: The test rejector.
        :return: True if this is a canary test.
        """
        return True if self.canary_pattern.match(test.test) else False

    def has_minimum_points(self, test):
        """
        Check if the minimum number of data points are available.
        :param TestAutoRejector test: The test rejector.
        :return: True if the minimum number of data points are available.
        """
        return test.full_series['size'] >= self.config.minimum_points

    def too_many_rejections(self, test):
        """
        Check if there are too many consecutive rejections.
        :param TestAutoRejector test: The test rejector.
        :return: True if there are too many consecutive rejections.
        """
        consecutive_fails = 0
        for status in reversed(test.full_series['rejected']):
            if status:
                consecutive_fails += 1
            else:
                break
        return consecutive_fails >= self.config.max_consecutive_rejections

    def latest(self, test):
        """
        Check if this task is the latest. Latest in this case means the task 'order' value is
        greater than or equal to the last order in the perf.points collection for the given
        test_identifier (project / variant / task / test).
        :param TestAutoRejector test: The test rejector.
        :return: True if this is a the latest task.
        """
        latest_order = test.full_series['orders'][-1]
        return self.order >= latest_order

    @property
    def whitelisted(self):
        """
        Check if this task is whitelisted.
        :return: True if this task is whitelisted.
        """
        if self._whitelisted is None:
            whitelist_collection = self.points_model.db[WHITELISTED_OUTLIER_TASKS]
            whitelist_query = dict(revision=self.revision, **self.task_identifier)
            whitelisted = whitelist_collection.find_one(whitelist_query)
            LOG.debug('whitelisted', found=whitelisted)
            self._whitelisted = whitelisted is not None
        return self._whitelisted


@nottest
class TestAutoRejector(object):
    """
    A class to apply the rules for automatic outlier detection for a task (a group of tests).

    A test is classed as automatic failures iff:
     * it is not part of a patch run.
     * it is part of the latest revision (run by evergreen).
     * there are no correctness issues.
     * >= 15 data point available from the previous change point.
     * the task is not muted.
     * the consecutive failure limit not reach (3 consecutive cumulative failures).
    """

    # pylint: disable=too-few-public-methods,too-many-arguments, too-many-instance-attributes
    def __init__(self, result, task, override_config):
        """
        :param dict result: The outlier test results for this test.
        :param TaskAutoRejector task: The task auto detector.
        :param dict override_config: The override configuration from the user.
        """
        self.result = result
        self.task = task
        self.test_identifier = self.full_series['test_identifier']
        self.test = self.test_identifier['test']
        self.thread_level = self.test_identifier['thread_level']

        self.override_config = override_config

        self._consecutive_fails = None
        self._muted = None
        self._outlier_orders = None
        self._config = None
        self._canary_pattern = None

        self._canary = None
        self._has_minimum_points = None
        self._too_many_rejections = None
        self._latest = None

    @property
    def config(self):
        if self._config is None:
            configurations = self.task.configuration_model.get_configuration(self.test_identifier)
            self._config = combine_outlier_configs(self.test_identifier, configurations,
                                                   self.override_config)
        return self._config

    @property
    def full_series(self):
        """
        Check if this task is a canary.
        :return: True if this is a canary task.
        """
        return self.result.full_series

    @property
    def canary(self):
        """
        Check if this test is a canary. This invocation defers to the task.
        :return: True if this is a canary test.
        """
        if self._canary is None:
            self._canary = self.task.canary(self)
        return self._canary

    @property
    def has_minimum_points(self):
        """
        Check if the minimum number of data points are available. This invocation defers to the
        task.
        :return: True if the minimum number of data points are available.
        """
        if self._has_minimum_points is None:
            self._has_minimum_points = self.task.has_minimum_points(self)
        return self._has_minimum_points

    @property
    def too_many_rejections(self):
        """
        Check if there are too many consecutive rejections. This invocation defers to the task.
        :return: True if there are too many consecutive rejections.
        """
        if self._too_many_rejections is None:
            self._too_many_rejections = self.task.too_many_rejections(self)
        return self._too_many_rejections

    @property
    def latest(self):
        """
        Check if this task is the latest. Latest in this case means the task 'order' value is
        greater than or equal to the last order in the perf.points collection for the given
        test_identifier (project / variant / task / test).
        :return: True if this is a the latest task.
        """
        if self._latest is None:
            self._latest = self.task.latest(self)
        return self._latest

    @property
    def muted(self):
        """
        Check if this task is muted.
        :return: True if this task is muted.
        """
        if self._muted is None:
            mutes_collection = self.task.points_model.db[MUTE_OUTLIERS]
            mute = mutes_collection.find(self.test_identifier) \
                .sort('order', pymongo.DESCENDING) \
                .limit(1)
            mute = next(mute, None)

            self._muted = \
                mute is not None and \
                mute.get('enabled', True) and \
                not mute_expired(mute, self.task.points_model.db.points)  # yapf: disable
        return self._muted

    @property
    def outlier_orders(self):
        """
        Get the list of orders that are outliers.
        :return: A list of orders that are outliers.
        """
        if self._outlier_orders is None:
            outlier_orders = []
            if self.result.gesd_result and self.result.gesd_result.count:
                count = self.result.gesd_result.count
                orders = self.result.full_series['orders']
                outlier_indexes = self.result.adjusted_indexes[:count]
                outlier_orders = [orders[index] for index in outlier_indexes]
            self._outlier_orders = outlier_orders
        return self._outlier_orders

    def reject(self, order):
        """
        Check if this test should be rejected based on:
            * order is in the list of outliers.
            * this is a canary test
            * it is not muted
            * it does not have too many rejections (more than 3)
            * there are more than 5 data points
            * it is the latest test result
        :param int order: The order to check.
        :return: True if this test should be rejected.
        """
        rejected = order in self.outlier_orders and \
               self.canary and \
               not self.muted and \
               not self.too_many_rejections and \
               self.has_minimum_points and \
               self.latest

        LOG.debug(
            'reject',
            order=order,
            outlier=order in self.outlier_orders,
            canary=self.canary,
            test=self.test,
            not_muted=not self.muted,
            not_too_many=not self.too_many_rejections,
            has_minimum_points=self.has_minimum_points,
            points=self.result.full_series['size'],
            latest=self.latest,
            rejected=rejected)
        return rejected
