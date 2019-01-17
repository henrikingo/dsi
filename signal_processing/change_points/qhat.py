"""
Computes the qhat e.divisive means change points.
"""
from __future__ import print_function

import os
from collections import OrderedDict
from contextlib import contextmanager
import copy
import random
import structlog
import numpy as np

from analysis.evergreen.helpers import get_githashes_in_range_github, get_githashes_in_range_repo
from signal_processing.change_points.range_finder import generate_start_and_end
from signal_processing.change_points.range_finder import link_ordered_change_points
import signal_processing.native.qhat

LOG = structlog.getLogger(__name__)


# QHat's definition requires it to permute change-windows
# which leads to non-determinism: we need to always get the
# same change-point results when running on the same input.
@contextmanager
def deterministic_random(seed):
    """
    Call random.seed(seed) during invocation and then restore state after.
    :param seed: RNG seed
    """
    state = random.getstate()
    random.seed(seed)
    try:
        yield
    finally:
        random.setstate(state)


MAJOR_REGRESSION_MAGNITUDE = np.log(1 / np.e**.5)
"""
The magnitude threshold for categorizing a change point as a major regression.
See :method:`calculate_magnitude` for more details.
"""

MODERATE_REGRESSION_MAGNITUDE = np.log(1 / np.e**.2)
"""
The magnitude threshold for categorizing a change point as a moderate regression.
See :method:`calculate_magnitude` for more details.
"""

MINOR_REGRESSION_MAGNITUDE = 0
"""
The magnitude threshold for categorizing a change point as a minor regression.
See :method:`calculate_magnitude` for more details.
"""

MAJOR_IMPROVEMENT_MAGNITUDE = np.log(np.e**.5)
"""
The magnitude threshold for categorizing a change point as a major improvement.
See :method:`calculate_magnitude` for more details.
"""

MODERATE_IMPROVEMENT_MAGNITUDE = np.log(np.e**.2)
"""
The magnitude threshold for categorizing a change point as a moderate improvement.
See :method:`calculate_magnitude` for more details.
"""


def calculate_magnitude(statistics):
    """
    Given a change point, calculate the magnitude. The magnitude is:

        1. log(next_mean / previous_mean) for throughput values
        2. log(previous_mean / next_mean) for latency values.

    :param dict statistics: The statistics to use to calculate the magnitude.
    :return: The magnitude along with a corresponding category.
    :rtype: tuple(float, str).
    """
    if not statistics or not statistics.get('previous', None) or not statistics.get('next', None):
        return None, 'Uncategorized'

    previous_mean = statistics['previous']['mean']
    next_mean = statistics['next']['mean']
    if previous_mean == 0 and next_mean == 0:
        magnitude = 0
    elif previous_mean == 0:
        magnitude = float('inf')
    elif next_mean == 0:
        magnitude = float('-inf')
    elif next_mean >= 0 and previous_mean >= 0:
        magnitude = np.log(float(next_mean) / float(previous_mean))
    else:
        # Currently, the collection and storage of metrics is primitive in that a higher number
        # always means better and lower always means worse. Thus for latencies, we negate the
        # results. This will change with the Expanded Metrics project and so will the means for
        # determining the type of result we are dealing with. In other words, once the project is
        # complete, we should not distinguish a latency metric by its sign; there will be more
        # sophisticated ways of doing so.
        # TODO: PM-965: `Expanded Metrics Collection (Latency, Distribution, Percentiles)`.
        magnitude = np.log(float(previous_mean) / float(next_mean))

    if magnitude < MAJOR_REGRESSION_MAGNITUDE:
        category = 'Major Regression'
    elif magnitude < MODERATE_REGRESSION_MAGNITUDE:
        category = 'Moderate Regression'
    elif magnitude < MINOR_REGRESSION_MAGNITUDE:
        category = 'Minor Regression'
    elif magnitude > MAJOR_IMPROVEMENT_MAGNITUDE:
        category = 'Major Improvement'
    elif magnitude > MODERATE_IMPROVEMENT_MAGNITUDE:
        category = 'Moderate Improvement'
    else:
        category = 'Minor Improvement'

    return magnitude, category


class QHatNumpyImp(object):  # pylint: disable=too-many-instance-attributes
    """
    Class to compute the qhat e.divisive means change points.
    """
    KEYS = ('index', 'value', 'value_to_avg', 'value_to_avg_diff', 'average', 'average_diff',
            'window_size', 'probability')

    # pylint: disable=too-many-arguments
    def __init__(self,
                 state,
                 pvalue=None,
                 permutations=None,
                 weighting=None,
                 mongo_repo=None,
                 credentials=None):
        """
        This class implements the QHat e.divisive algorithm in python.

        :param dict state: The input data for the calculations. This contains the time series
        performance data ('series') and the meta data (like 'revisions', 'orders', 'create_times',
        'threads' and 'testname') to help identify the location of any calculated change points.
        :param float pvalue: This the significance level for our testing.
        See 'P-value<https://en.wikipedia.org/wiki/P-value>'.
        :param int permutations: The max number of permutations to perform when evaluating the
        pvalue significance testing.
        :param float weighting: A value used to seed the decay weights array when finding the start
        / end positions of the actual change point.
        :param str mongo_repo: The mongo git repo location.
        :param dict credentials: The github token.
        TODO: Remove weighting, repo and credentials when fixing PERF-1608.
        """
        self.state = state
        self.series = self.state.get('series', None)
        self.revisions = self.state.get('revisions', None)
        self.orders = self.state.get('orders', None)
        self.testname = self.state.get('testname', None)
        self.threads = self.state.get('threads', None)
        self.create_times = self.state.get('create_times', None)
        self.thread_level = self.state.get('thread_level', None)

        self._id = self.state.get('_id', None)

        self._change_points = state.get('change_points', None)
        self.pvalue = 0.05 if pvalue is None else pvalue
        self.weighting = 0.001 if weighting is None else weighting
        self.permutations = 100 if permutations is None else permutations
        self._windows = state.get('windows', None)
        self._min_change = state.get('min_change', None)
        self._max_q = state.get('max_q', None)
        self._min_change = state.get('min_change', None)
        self.dates = state.get('dates', None)
        self.length = None
        self.average_value = None
        self.average_diff = None

        self.mongo_repo = mongo_repo
        self.credentials = credentials

        if self.series is None:
            self.series = []
        if not isinstance(self.series, np.ndarray):
            self.series = np.array(self.series, np.float)

    def extract_q(self, qhat_values):
        """
        Given an ordered sequence of Q-Hat values, output the max value and index

        :param list qhat_values: qhat values
        :return: list (max , index, etc)
        """
        if qhat_values.size:
            max_q_index = np.argmax(qhat_values)
            # noinspection PyTypeChecker
            max_q = qhat_values[max_q_index]
        else:
            max_q = 0
            max_q_index = 0

        return [
            max_q_index, max_q, max_q / self.average_value
            if self.average_value != 0 else float('nan'), max_q / self.average_diff
            if self.average_diff != 0 else float('nan'), self.average_value, self.average_diff,
            self.length
        ]

    @staticmethod
    def calculate_q(term1, term2, term3, m, n):
        """
        Calculate the q value from the terms and coefficients.

        :param float term1: The current cumulative value for the first
        term in the QHat algorithm. This is the sum of the differences to
        the right of the current location.
        :param float term2: The current cumulative value for the second
        term in the QHat algorithm. This is the sum of the differences to
        the at the current location.
        :param float term3: The current cumulative value for the third
        term in the QHat algorithm. This is the sum of the differences to
        the left of the current location.
        :param int m: The current row location.
        :param int n: The current column location.

        :return: The q value generated from the terms.
        :rtype: float.
        """
        term1_reg = term1 * (2.0 / (m * n))
        term2_reg = term2 * (2.0 / (n * (n - 1)))
        term3_reg = term3 * (2.0 / (m * (m - 1)))
        newq = (m * n / (m + n)) * (term1_reg - term2_reg - term3_reg)
        return newq

    @staticmethod
    def calculate_diffs(series):
        """
        Given an array N calculate an NxN difference matrix.

        :param list(float) series: The array to calculate the matrix for.

        :return: The difference matrix.
        :rtype: list(list(float)).
        """
        row, col = np.meshgrid(series, series)
        diffs = abs(row - col)
        return diffs

    # Implementing change-point detection algorithm from https://arxiv.org/pdf/1306.4933.pdf
    def qhat_values(self, series):  #pylint: disable=too-many-locals,too-many-branches
        """
        Check the input values, calculate the diffs matrix and delegate to calculate_qhat_values.

        :param list series: the points to process
        :return: The qhat values.
        :rtype: np.array(float).
        """

        # used as the window size in extract_q
        self.length = len(series)
        qhat_values = np.zeros(self.length, dtype=np.float)
        if self.length < 5:
            # Average value and average diff are used even when there is no data.
            # This avoids an error.
            self.average_value = 1
            self.average_diff = 1
            return qhat_values

        return self.calculate_qhat_values(series, None, qhat_values)

    def calculate_qhat_values(self, series, diffs, qhat_values):
        #pylint: disable=too-many-locals,too-many-branches,unused-argument
        """
        Find Q-Hat values for all candidate change points. This provides the current
        'best' python implementation. The intention is to override this for other
        implementations, say a native implementation.

        :param numpy.array(float) series: The points to process.
        :param numpy.array(float) qhat_values: The array to store the qhat values.
        :param numpy.2darray(float) diffs: The matrix of diffs.
        :return: The qhat values.
        :rtype: numpy.array(float).
        """
        diffs = self.calculate_diffs(series)

        self.average_value = np.average(series)
        self.average_diff = np.average(diffs)

        n = 2
        m = self.length - n

        # Each line is preceded by the equivalent list comprehension.

        # term1 = sum(diffs[i][j] for i in range(n) for j in range(n, self.window)) # See qhat.md
        term1 = np.sum(diffs[:n, n:])

        # term2 = sum(diffs[i][k] for i in range(n) for k in range(i + 1, n)) # See qhat.md
        term2 = np.sum(np.triu(diffs[:n, :n], 0))

        # term3 = sum(diffs[j][k] for j in range(n, self.window)
        #                         for k in range(j + 1, self.window)) # See qhat.md
        term3 = np.sum(np.triu(diffs[n:, n + 1:], 0))

        qhat_values[n] = self.calculate_q(term1, term2, term3, m, n)

        for n in range(3, (self.length - 2)):
            m = self.length - n
            column_delta = np.sum(diffs[n - 1, :n - 1])
            row_delta = np.sum(diffs[n:, n - 1])

            term1 = term1 - column_delta + row_delta
            term2 = term2 + column_delta
            term3 = term3 - row_delta

            qhat_values[n] = self.calculate_q(term1, term2, term3, m, n)

        return qhat_values

    @property
    def change_points(self, seed=1234):
        """
        Property to access change points.

        :raises: FloatingPointError for numpy errors.
        :see: 'numpy.seterr
        <https://docs.scipy.org/doc/numpy-1.15.0/reference/generated/numpy.seterr.html>'
        :see: 'numpy.errstate
        <https://docs.scipy.org/doc/numpy-1.15.0/reference/generated/numpy.errstate.html>'
        """
        with deterministic_random(seed), np.errstate(all='raise'):
            return self._compute_change_points()

    def _compute_change_points(self):  # pylint: disable=too-many-locals
        """
        Compute the change points. This is lazy and only runs once.
        """
        if self._change_points is None:
            LOG.info("compute_change_points")
            windows = []
            pts = len(self.series)
            qhat_values = self.qhat_values(self.series)
            LOG.debug("compute_change_points", qs=qhat_values, series=self.series)
            first_q = self.extract_q(qhat_values)
            max_q = first_q[1]
            min_change = max_q
            change_points = []

            # HIERARCHICALLY COMPUTE OTHER CHANGEPOINTS
            terminated = False
            while not terminated:
                candidates = []
                windows = [0] + sorted([c[0] for c in change_points]) + [pts]
                LOG.debug("compute_change_points", windows=windows)
                for i in range(len(windows) - 1):
                    window = self.series[windows[i]:windows[i + 1]]
                    win_qs = self.qhat_values(window)
                    win_max = self.extract_q(win_qs)
                    win_max[0] += windows[i]
                    candidates.append(win_max)
                    LOG.debug(
                        "compute_change_points candidate",
                        win_qs=win_qs,
                        series=window,
                        win_max=win_max)
                candidates.sort(key=lambda tup: tup[1])
                candidate_q = candidates[len(candidates) - 1][1]
                LOG.debug("compute_change_points", candidate_q=candidate_q)

                # RANDOMLY PERMUTE CLUSTERS FOR SIGNIFICANCE TEST

                above = 0.0  # results from permuted test >= candidate_q
                for i in range(self.permutations):
                    permute_candidates = []
                    for j in range(len(windows) - 1):
                        window = copy.copy(self.series[windows[j]:windows[j + 1]])
                        random.shuffle(window)
                        win_qs = self.qhat_values(window)
                        win_max = self.extract_q(win_qs)
                        win_max = (win_max[0] + windows[j], win_max[1])
                        permute_candidates.append(win_max)
                        LOG.debug(
                            "compute_change_points", candidate_q=candidate_q, candidates=candidates)
                    permute_candidates.sort(key=lambda tup: tup[1])
                    permute_q = permute_candidates[len(permute_candidates) - 1][1]
                    LOG.debug("compute_change_points", permute_q=permute_q)
                    if permute_q >= candidate_q:
                        above += 1

                # for coloring the lines, we will use the first INSIGNIFICANT point
                # as our baseline for transparency
                if candidate_q < min_change:
                    min_change = candidate_q

                probability = above / (self.permutations + 1)
                if probability > self.pvalue:
                    terminated = True
                else:
                    change_points.append(list(candidates[len(candidates) - 1]) + [probability])

            self._change_points = self.add_to_change_points(change_points, 'qhat', QHat.KEYS)
            self._windows = windows
            self._min_change = min_change
            self._max_q = max_q
            LOG.debug("_compute_change_points", change_points=self._change_points)

        return self._change_points

    def get_git_hashes(self, older_revision, newer_revision):
        """
        Get git hashes from local git repo or github.

        :param str newer_revision: The newest git hash.
        :param str older_revision: The oldest git hash.
        :return: All the git hashes between older and newer (excluding older). The
        order is from newer to older.
        TODO: Move out as part PERF-1608.
        """
        LOG.debug(
            "getting githashes from repo",
            mongo_repo=self.mongo_repo,
            newer_revision=newer_revision,
            older_revision=older_revision)

        git_hashes = None
        # pylint: disable=bare-except
        try:
            git_hashes = get_githashes_in_range_repo(older_revision, newer_revision,
                                                     self.mongo_repo)
            LOG.debug("githashes from repo", git_hashes=git_hashes)
        except:
            LOG.error("unexpected error on rev-list", exc_info=1)

        if git_hashes is None:
            github_token = None
            if self.credentials and 'token' in self.credentials:
                github_token = self.credentials['token']
            LOG.debug(
                "getting githashes from github",
                mongo_repo=self.mongo_repo,
                token=True if github_token else False,
                newer_revision=newer_revision,
                older_revision=older_revision)
            try:
                git_hashes = [
                    commit['sha']
                    for commit in get_githashes_in_range_github(
                        older_revision, newer_revision, token=github_token, per_page=100)
                ]
                LOG.debug("githashes from github", git_hashes=git_hashes)
            except:
                LOG.error("unexpected error in get git hashes", exc_info=1)
                git_hashes = []
        LOG.debug("loaded git hashes", git_hashes=git_hashes)
        return git_hashes

    def add_to_change_points(self, change_points, algorithm_name, keys):
        # pylint: disable=too-many-locals
        """
        Update raw change points to:
            1) Sort the change point indexes.
            2) Use the sorted change point indexes to get the start end ranges.
            3) Use the start / end ranges to create a list of change points including the ranges.
            4) Calculate descriptive stats from series[prev:start] and series[end:next]
            5) Create change point dicts from this data.

        :param list(list) change_points: The raw change points data.
        :param str algorithm_name: The algorithm name.
        :param list(str) keys: The  names for the values in change_points.

        :return: The change points in order of probability.
        :rtype: list(dict).
        TODO: Consider moving out as part PERF-1608.
        """
        points = []
        sorted_indexes = sorted([point[0] for point in change_points])
        start_ends = generate_start_and_end(sorted_indexes, self.series, weighting=self.weighting)
        link_ordered_change_points(start_ends, self.series)

        for order_of_change_point, point in enumerate(change_points):
            # Find the index of the change point in the range finder output.
            range_index = next(
                i for i, start_end in enumerate(start_ends) if point[0] == start_end['index'])
            current_range = start_ends[range_index]

            # Create a dict for the algorithm output. This is saved as a sub-document
            # in the change point.
            algorithm = OrderedDict([('name', algorithm_name)])
            algorithm.update((key, point[i]) for i, key in enumerate(keys))

            # Get the revision flagged by qhat and add it to the
            # calculations to track.
            algorithm['revision'] = self.revisions[algorithm['index']]

            # Create a dict fort the range finder state. This is saved as
            # a sub-document in the change point.
            range_finder = OrderedDict([('weighting', self.weighting)]) # yapf: disable

            # Start to colate the information we want to put at the top-level
            # of the change point

            # This represents the last stable revision before the change in
            # performance.
            stable_revision_index = current_range['start']  # oldest
            stable_revision = self.revisions[stable_revision_index]  # oldest

            # This represents the first githash that displays the change
            # in performance. It may not be the root cause. There may
            # be older unrun revisions (between this and the stable
            # revision).
            # Put this value in the BF first fail or fix revision
            suspect_revision_index = current_range['end']
            suspect_revision = self.revisions[suspect_revision_index]  # newest

            # The complete set of git hashes between the suspect / newer revision
            # (included in the list) to the stable / older revision (excluded from
            # the list) to the . The order is from newest to oldest
            # so supsect revision is the first element in the list.
            # Any change in performance must be as a result of one of the
            # revisions in this list (assuming the change point is real and
            # as a result of some code change).
            all_suspect_revisions = self.get_git_hashes(stable_revision, suspect_revision)

            magnitude, category = calculate_magnitude(current_range.get('statistics', {}))

            probability = 1.0 - algorithm['probability']

            point = OrderedDict([('thread_level', self.thread_level),
                                 ('suspect_revision', suspect_revision),
                                 ('all_suspect_revisions', all_suspect_revisions),
                                 ('probability', probability),
                                 ('create_time', self.create_times[suspect_revision_index]),
                                 ('value', self.series[suspect_revision_index]),
                                 ('order', self.orders[suspect_revision_index]),
                                 ('order_of_change_point', order_of_change_point),
                                 ('statistics', current_range.get('statistics', {})),
                                 ('range_finder', range_finder),
                                 ('algorithm', algorithm),
                                 ('magnitude', magnitude),
                                 ('category', category)]) # yapf: disable
            points.append(point)

            LOG.debug("algorithm output", points=points)

        return points

    @property
    def windows(self):
        """
        Get the windows used by the algorithm.
        """
        if self._windows is None:
            _ = self.change_points
        return self._windows

    @property
    def min_change(self):
        """
        Min Change.
        """
        if self._min_change is None:
            _ = self.change_points
        return self._min_change

    @property
    def max_q(self):
        """
        Get the maximum q value.
        """
        if self._max_q is None:
            _ = self.change_points
        return self._max_q


DSI_DISABLE_NATIVE_QHAT = os.environ.get('DSI_DISABLE_NATIVE_QHAT',
                                         'false').lower() in ['true', 't']
if not DSI_DISABLE_NATIVE_QHAT and signal_processing.native.qhat.LOADED:

    class QHatNativeImp(QHatNumpyImp):  #pylint: disable=too-many-instance-attributes
        """
        Derive a new class and use the native qhat implementation.
        """

        def calculate_qhat_values(self, series, diffs, qhat_values):  #pylint: disable=too-many-locals,too-many-branches
            # used as the window size in extract_q
            diffs = signal_processing.native.qhat.qhat_diffs_wrapper(series)

            self.average_value = np.average(series)
            self.average_diff = np.average(diffs)
            signal_processing.native.qhat.qhat_values_wrapper(series, diffs, qhat_values)
            return qhat_values

    QHat = QHatNativeImp
else:
    if not signal_processing.native.qhat.LOADED:
        LOG.warn(
            'falling back to numpy optimized QHat',
            loaded=signal_processing.native.qhat.LOADED,
            DSI_DISABLE_NATIVE_QHAT=DSI_DISABLE_NATIVE_QHAT)
    else:
        LOG.info(
            'falling back to numpy optimized QHat',
            loaded=signal_processing.native.qhat.LOADED,
            DSI_DISABLE_NATIVE_QHAT=DSI_DISABLE_NATIVE_QHAT)
    QHat = QHatNumpyImp
