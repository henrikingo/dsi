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
import re

import pymongo
import structlog
from nose.tools import nottest

from signal_processing.detect_changes import PointsModel
from signal_processing.outliers.list_mutes import mute_expired

STATUS_PASS = 'pass'
"""
A test has passed.
"""

STATUS_FAIL = 'fail'
"""
A test has failed.
"""

DEFAULT_CANARY_PATTERN = re.compile('^(canary_.*|fio_.*|iperf.*|NetworkBandwidth)$')
"""
The default pattern for canary test names. In this case, the test name starts with one of:
  * canary
  * fio
  * NetworkBandwidth
"""

CORRECTNESS_PATTERNS = [
    re.compile(pattern)
    for pattern in ('^db-hash-check', '^validate-indexes-and-collections', '^core\\.')
]
"""
Any test_file matching one of these patterns is a correctness error.
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
    def __init__(self,
                 results,
                 project,
                 variant,
                 task,
                 order,
                 mongo_uri,
                 patch,
                 status,
                 max_consecutive_rejections=3,
                 minimum_points=15,
                 canary_pattern=None):
        """
        :param list(dict) results: The outlier test results for this task.
        :param str project: The project name for this task.
        :param str variant: The variant for this task.
        :param str task: The task name for this task.
        :param int order: The order value for this task.
        :param str mongo_uri: The uri to connect to the cluster.
        :param bool patch: True if this is a patch.
        :param dict status: The task status.
        :param canary_pattern: The pattern for a canary test. None uses the default pattern.
        :type canary_pattern: str or None.
        :param int max_consecutive_rejections: The number of fails to reject, if there are more
        than this number of fails then skip rejecting.
        :param int minimum_points: The minimum number of data points required to reject a result.
        """
        self.results = [
            TestAutoRejector(result, self, max_consecutive_rejections, minimum_points)
            for result in results
        ]
        self.max_consecutive_rejections = max_consecutive_rejections
        self.minimum_points = minimum_points

        self.project = project
        self.variant = variant
        self.task = task

        self.order = order
        self.mongo_uri = mongo_uri
        self.patch = patch
        self.status = status
        self._model = None

        if canary_pattern is None:
            self.canary_pattern = DEFAULT_CANARY_PATTERN
        else:
            if isinstance(self.canary_pattern, str):
                self.canary_pattern = re.compile(self.canary_pattern)
        assert isinstance(self.canary_pattern, type(re.compile("", 0)))

        self._correct = None
        self._failed_correctness_reports = None

        self._rejects = None

    @property
    def model(self):
        """
        Get a reference to the PointsModel Object.
        :return: The PointsModel instance (lazy evaluated).
        :rtype: detect_changes.PointsModel
        """
        if self._model is None:
            self._model = PointsModel(self.mongo_uri)
        return self._model

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
                    all_tests = self.status['results']
                    self._failed_correctness_reports = [
                        result['test_file'] for result in all_tests
                        if any(
                            regex.match(result['test_file'])
                            for regex in CORRECTNESS_PATTERNS) and result['status'] == STATUS_FAIL
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
            result for result in self.rejects if not self.patch and self.correct and result.reject
        ]
        LOG.debug('filtered rejects list', rejects=rejects)
        return rejects


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
    def __init__(self, result, task, max_consecutive_rejections, minimum_points):
        """
        :param dict result: The outlier test results for this test.
        :param TaskAutoRejector task: The task auto detector.
        :param int max_consecutive_rejections: The number of fails to reject, if there are more
        than this number of fails then skip rejecting.
        :param int minimum_points: The minimum number of data points required to reject a result.
        """
        self.result = result
        self.task = task
        self.test_identifier = self.full_series['test_identifier']
        self.test = self.test_identifier['test']
        self.thread_level = self.test_identifier['thread_level']

        self.max_consecutive_rejections = max_consecutive_rejections
        self.minimum_points = minimum_points

        self._consecutive_fails = None
        self._muted = None
        self._outlier_orders = None

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
        Check if this task is a canary.
        :return: True if this is a canary task.
        """
        return True if self.task.canary_pattern.match(self.test) else False

    @property
    def has_minimum_points(self):
        """
        Check if the minimum number of data points are available.
        :return: True if the minimum number of data points are available.
        """
        return self.result.full_series['size'] >= self.minimum_points

    @property
    def too_many_rejections(self):
        """
        Check if there are too many consecutive rejections.
        :return: True if there are too many consecutive rejections.
        """
        if self._consecutive_fails is None:
            self._consecutive_fails = 0
            for status in reversed(self.result.full_series['rejected']):
                if status:
                    self._consecutive_fails += 1
                else:
                    break
        return self._consecutive_fails >= self.max_consecutive_rejections

    @property
    def muted(self):
        """
        Check if this task is muted.
        :return: True if this task is muted.
        """
        if self._muted is None:
            mutes_collection = self.task.model.db['mute_outliers']
            mute = mutes_collection.find(self.test_identifier) \
                .sort('order', pymongo.DESCENDING) \
                .limit(1)
            mute = next(mute, None)

            self._muted = mute is not None and not mute_expired(mute, self.task.model.db.points)
        return self._muted

    @property
    def latest(self):
        """
        Check if this task is the latest. Latest in this case means the task 'order' value is
        greater than or equal to the last order in the perf.points collection for the given
        test_identifier (project / variant / task / test).
        :return: True if this is a the latest task.
        """
        latest_order = self.full_series['orders'][-1]
        return self.task.order >= latest_order

    @property
    def outlier_orders(self):
        """
        Get the list of orders that are outliers.
        :return: A list of orders that are outliers.
        """
        if self._outlier_orders is None:
            count = self.result.gesd_result.count
            if count:
                orders = self.result.full_series['orders']
                outlier_indexes = self.result.adjusted_indexes[:count]
                self._outlier_orders = [orders[index] for index in outlier_indexes]
            else:
                self._outlier_orders = []
        return self._outlier_orders

    @property
    def reject(self):
        """
        Check if this test should be rejected based on:
            * this is a canary test
            * it is not muted
            * it does not have too many rejections (more than 3)
            * there are more than 5 data points
            * it is the latest test result
        :return: True if this test should be rejected.
        """
        return self.canary and \
               not self.muted and \
               not self.too_many_rejections and \
               self.has_minimum_points and \
               self.latest
