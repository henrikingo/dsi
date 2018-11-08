"""
Computes the qhat e.divisive means change points.
"""
from __future__ import print_function

import os
from collections import OrderedDict
from contextlib import contextmanager
import copy
import itertools
import random
import structlog
import numpy as np

from scipy import stats
from scipy.stats import expon

from analysis.evergreen.helpers import get_githashes_in_range_github, get_githashes_in_range_repo
import signal_processing.native.qhat

DEFAULT_FIGIZE = (18, 8)

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


LOCATION_BEHIND = 'behind'
"""
The location refers to whether we need to search forward in history from the candidate commit, or
backwards.
See :method:`get_location` for more details.
"""

LOCATION_AHEAD = 'ahead'
"""
The location refers to whether we need to search forward in history from the candidate commit, or
backwards.
See :method:`get_location` for more details.
"""

DEFAULT_WEIGHTING = .001
"""
The default value to use to generate the weightings.
See :method:`linear_weights` and `exponential_weights` for more details.
"""

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


def linear_weights(size, weighting):
    """
    Create an array of linearly decaying values. The calling code should flip the return value if
    required.

    :param int size: The length of the generated weights array.
    :param weighting: The percentage difference between points.
    :return: An array of weights to multiply against the values to grow or decay them.
    :rtype: list(float).
    TODO: Move as part of PERF-1608.
    """
    weights = np.array([1 - weighting * i for i in range(size - 1, -1, -1)], dtype=np.float64)
    return weights


def exponential_weights(size, weighting):
    """
    Create an array of exponentially decaying values. The calling code should flip the return value
    if required.

    The values selected are from the formula:

        f(x) = exp(-x) # the probability density function for expon

    Some examples (the values produced are floats, they are expressed here as percentages for
    clarity):

        .001 weighting produces the following:

            100%  55% 30% 16% 9% 5% 2% 1.5% .8% .4$

            _So 100% of the first value is retained, 55% of the second and so on._

        .0001 weighting produces the following:

            100%  43% 19% 8% 3.6% 1.5% .6% .3% .1% .05$


        .1 * 100 weighting produces the following:

            100%  87% 76% 67% 59% 51% 45% 39% 34% 30$

    A lower weighting decays quickly and a higher weighting decays more slowly. This allows the
    points closer to the filtered or not.

    The logic behind this approach is that linear decay is constant so it is insensitive.
    Exponential decay allows a greater range / type of values to be generated depending on the
    exact value of weighting.

    :param int size: The length of the generated weights array.
    :param weighting: The percentage difference between points.
    :return: An array of weights to multiply against the values to grow or decay them.
    :rtype: list(float).

    See `expon<https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.expon.html>`
    See `ppf<https://en.wikipedia.org/wiki/Quantile_function>`.
    TODO: Move as part of PERF-1608.
    """
    # create at least 100 or size evenly spaced numbers from 1 to ppf(1 - weighting).
    # ppf is probability of the variable being less than or equal to that value.
    x = np.linspace(1.0, expon.ppf(1 - weighting), min(size, 100))
    random_variable = expon()

    # get the probability density variable for x and select every 10 element.
    pdf = random_variable.pdf(x)
    weights = pdf[0:min(size, 100) * 10:10]

    # normalize to start at 1 (weights[0] is the max value).
    weights = weights / weights[0]
    return weights


def get_location(behind_average, value, ahead_average):
    """
    The change point reported by qhat is often not going to be the exact commit that introduced the
    change, in part because we don't run on every commit. We need to search for (and run) the
    commit that introduced the change.

    This method examines the means (of the behind and ahead ranges) and current value to determine
    the location to search (ahead or behind).

    This information will later be used to search ahead or behind.

    :param float behind_average: The mean value of the series behind the value.
    :param int value: The value flagged as a change point.
    :param float ahead_average: The mean value of the series ahead of value.
    :return: The location.
    :rtype: tuple(str, str).
    TODO: Move as part of PERF-1608.
    """
    diff_to_behind_mean = behind_average - value
    diff_to_ahead = ahead_average - value

    if abs(diff_to_ahead) > abs(diff_to_behind_mean):
        location = LOCATION_AHEAD
    else:
        location = LOCATION_BEHIND

    LOG.debug("calc location", location=location)
    return location


def select_start_end(input_series, prev_index, index, next_index, weighting, bounds=1):
    # pylint: disable=too-many-arguments, too-many-locals, too-many-branches
    """
    To state it simply, we want to find the index that is furthest away from the desired mean line
    (the one that has the greatest difference to value) but which is as close as possible to index
    (as this point has been chosen by qhat).

    The change point reported by qhat is often not going to be the exact commit that introduced
    the change, in part because we don't run on every commit. We need to search for (and run) the
    commit that introduced the change. The location refers to the need to search ahead
    in history from the candidate commit, or behind.

    This method selects a start and end index that encompasses the actual change point.

    The steps involved are:
    1) Determine the general location, behind for when the change point is less than index or
    ahead when it is greater of index.

    2) Create a multiplier based on the bounds and the weighting (so as to prefer closer
    points). Growth or decay in the values based the location and the distance from value. The
    weights are generated to give more consideration to points closer to the chosen qhat index.

    A low bounds is better or the code may select an outlier.

    3)  Depending on the location, We will search between:
         Backwards => (max(index - bounds + 1, prev_index), index + 1) or
         Forwards  => (index, min(index + bounds, next_index))

    attempting to maximize the square of the difference between the current value and the correct
    average (either the forward or backward range).
    Squaring the difference ensures that negatives don't cause issues. The index of the maxima is
    what we will use for start.

    4) Return start, start + 1, location. The actual change point should be between start and
    start + 1

    Within the (prev_index, start), (start + 1, next_index) ranges the variance should be minimal
    around the average (of each series).

    Essentially, we are assuming the time series data is stationary.

    See `Stationary process <https://en.wikipedia.org/wiki/Stationary_process>`.

    :param list(float) input_series: The performance data.
    :param int prev_index: The index of the previous change point (or 0).
    :param int index: The index of the current change point (or 0).
    :param int next_index: The index of the next change point (or len(series)).
    :param int bounds: The max number of points to consider.
    :param weighting: The weighting to apply to each value (exponential).
    :return: A tuple of (start, end, location).
    :rtype: tuple(int, int, str).
    TODO: Move as part of PERF-1608.
    """
    LOG.debug(
        "determine start end",
        series=zip(range(len(input_series)), input_series),
        prev_index=prev_index,
        index=index,
        next_index=next_index)

    # Handle rare edge cases.
    if next_index == prev_index:
        LOG.debug("next and prev are the same", next_index=next_index)
        return next_index, next_index, LOCATION_AHEAD

    series = np.array(input_series, dtype=np.float64)
    value = series[index]

    # Calculate the averages.
    behind_average = np.mean(series[prev_index:index - 1])
    ahead_average = np.mean(series[index + 1:next_index])

    if behind_average == ahead_average:
        LOG.debug("behind and ahead averages are the same", behind_average=behind_average)
        return index, index, LOCATION_AHEAD

    if np.isnan(ahead_average):
        ahead_average = series[index]
        location = LOCATION_BEHIND
        LOG.debug("nan", location=location)
    elif np.isnan(behind_average):
        behind_average = series[index]
        location = LOCATION_AHEAD
        LOG.debug("nan", location=location)
    else:
        # Get the location (ahead or behind).
        location = get_location(behind_average, value, ahead_average)
    LOG.debug("selected", location=location)

    # Set the start and end indexes, ensuring we don't overshoot.
    if location == LOCATION_BEHIND:
        start = max(index - bounds + 1, prev_index)
        end = index + 1
    else:
        start = index
        end = min(index + bounds, next_index)

    # Create our weightings, these values cause this code to prefer indexes closer to the
    # selection made by the algorithm. No reverse on np.array, so flip the the values where
    # appropriate for growth or decay. Flip may return a copy or a view.
    weights = exponential_weights(end - start, weighting)
    if location == LOCATION_AHEAD:
        weights = np.flip(weights, 0)

    # Get the correct range and subtract the correct average.
    points = series[start:end]
    if location == LOCATION_AHEAD:
        deltas = np.repeat(ahead_average, len(points))
    else:
        deltas = np.repeat(behind_average, len(points))
    points = points - deltas

    points = points * weights

    # Square the values, to ensure that we only have positive values and can maximize.
    points = np.square(points)
    position = np.argmax(points)

    # If we overshoot index then we need to pull back one.
    if position + 1 == len(points):
        position = position - 1

    start = start + position

    # If we overshoot the allowable range then we need to pull back.
    if start < prev_index:
        start = prev_index + 1
    if start > next_index:
        start = next_index - 1

    return start, start + 1, location


def generate_start_and_end(sorted_change_points, series, weighting=.001):
    """
    Given an ordered list of change points, calculate the start and end and update each in place.

    It is assumed that the change_points sorted.

    :param list(dict) sorted_change_points: The list of sorted change points.
    :param list(float) series: The series.
    :param float weighting: The weighting for the decay.
    :return: The updated list of change points.
    :rtype: list(dict).
    TODO: Move as part of PERF-1608.
    """
    start_ends = []
    if sorted_change_points:
        prev_index = 0
        for position, point in enumerate(sorted_change_points):
            if position + 1 < len(sorted_change_points):
                next_index = sorted_change_points[position + 1]
            else:
                next_index = len(series)

            start, end, location = select_start_end(
                series, prev_index, point, next_index, weighting=weighting)

            start_ends.append({'index': point, 'start': start, 'end': end, 'location': location})
            prev_index = end

    return start_ends


def generate_pairs(values):
    """
    Given a list of values, generate pairs.

    :param list values: The list of values.
    :return: The list as pairs of values.
    TODO: Move as part of PERF-1608.
    """

    if values:
        befores, afters = itertools.tee(values)
        next(afters, None)
        for before, after in itertools.izip(befores, afters):
            yield before, after


def describe_range(series, start, end, lookup):
    """
    Generate descriptive stats for range.

    :param list(float) series: The data.
    :param int start: The start index.
    :param int end: The end index.
    :param dict((int, int), stats) lookup: Lookup table for data.
    TODO: Consider Moving as part of PERF-1608.
    """
    if end != start:
        behind_range = (start, end)
        if end - start == 1:
            description = {
                'nobs': 1,
                'minmax': (series[start], series[start]),
                'mean': series[start],
                'variance': np.nan,
                'skewness': 0.0,
                'kurtosis': -3
            }
        else:
            description = lookup.get(behind_range, stats.describe(series[start:end])._asdict())
        lookup[behind_range] = description
        return description
    else:
        return None


def describe_change_point(change_point, series, lookup):
    """
    Generate descriptive stats for change_point. This calls describe_range twice (for behind and
    ahead).

    :param dict change_point: The populated change point. It must have previous, start, end and
    next set.
    :param list(float) series: The performance data.
    :param dict((int, int), stats) lookup: Lookup table for data.
    TODO: Consider Moving as part of PERF-1608.
    """
    description = {}
    previous = describe_range(series, change_point['previous'], change_point['start'], lookup)
    if previous:
        description['previous'] = previous

    to_next = describe_range(series, change_point['end'], change_point['next'], lookup)
    if to_next:
        description['next'] = to_next

    return description


def link_ordered_change_points(sorted_change_points, series):
    """
    Given an ordered list of change points, update each in place and set the prev and next index
    values (from the correct start and end values).

    It is assumed that the change_points are sorted.

    :param list(dict) sorted_change_points: The list of sorted change points.
    :param list(float) series: The series.
    :return: The updated list of change points.
    :rtype: list(dict).
    TODO: Consider Moving as part of PERF-1608.
    """
    if sorted_change_points:
        size = len(series)

        # change point
        # Field name
        # 'previous' ---->        'start' <--> 'end'    -----> 'next'
        #  (0 || prev['end'])                                   (next['start'] || len(series))
        sorted_change_points[0]['previous'] = 0
        sorted_change_points[-1]['next'] = size

        lookup = {}
        for current_change_point, next_change_points in generate_pairs(sorted_change_points):
            current_change_point['next'] = next_change_points['start']
            next_change_points['previous'] = current_change_point['end']

            descriptive = describe_change_point(current_change_point, series, lookup)
            if descriptive:
                current_change_point['statistics'] = descriptive

        current_change_point = sorted_change_points[-1]
        descriptive = describe_change_point(current_change_point, series, lookup)
        if descriptive:
            current_change_point['statistics'] = descriptive
    return sorted_change_points


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


class QHatNumpyImp(object):  #pylint: disable=too-many-instance-attributes
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
        <https://docs.scipy.org/doc/numpy-1.15.0/reference/generated/numpy.seterr.html>
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
