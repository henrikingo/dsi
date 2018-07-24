"""
Computes the qhat e.divisive means change points.
"""
from __future__ import print_function

from collections import OrderedDict
from contextlib import contextmanager
import copy
import itertools
import random
import structlog
import numpy as np

from matplotlib.ticker import FuncFormatter, MaxNLocator
from scipy import stats
from scipy.stats import expon

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


def linear_weights(size, weighting):
    """
    Create an array of linearly decaying values. The calling code should flip the return value if
    required.

    :param int size: The length of the generated weights array.
    :param weighting: The percentage difference between points.
    :return: An array of weights to multiply against the values to grow or decay them.
    :rtype: list(float).
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
    """
    diff_to_behind_mean = behind_average - value
    diff_to_ahead = ahead_average - value

    if abs(diff_to_ahead) > abs(diff_to_behind_mean):
        location = LOCATION_AHEAD
    else:
        location = LOCATION_BEHIND

    LOG.debug("calc location", location=location)
    return location


def select_start_end(input_series, prev_index, index, next_index, weighting, bounds=5):
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


def generate_pairs(values):
    """
    Given a list of values, generate pairs.

    :param list values: The list of values.
    :return: The list as pairs of values.
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


def generate_start_and_end(sorted_change_points, series, weighting=.001):
    """
    Given an ordered list of change points, calculate the start and end and update each in place.

    It is assumed that the change_points sorted.

    :param list(dict) sorted_change_points: The list of sorted change points.
    :param list(float) series: The series.
    :param float weighting: The weighting for the decay.
    :return: The updated list of change points.
    :rtype: list(dict).
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


class QHat(object):  #pylint: disable=too-many-instance-attributes
    """
    Class to compute the qhat e.divisive means change points.
    """
    KEYS = ('index', 'value', 'value_to_avg', 'value_to_avg_diff', 'average', 'average_diff',
            'window_size', 'probability')

    def __init__(self,
                 state,
                 pvalue=None,
                 permutations=None,
                 online=None,
                 threshold=None,
                 weighting=None):
        #pylint: disable=too-many-arguments
        """
        Constructor.
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

        _ = threshold

        self._change_points = state.get('change_points', None)
        self.pvalue = 0.05 if pvalue is None else pvalue
        self.weighting = 0.001 if weighting is None else weighting
        self.permutations = 100 if permutations is None else permutations
        self.online = 20 if online is None else online
        self._windows = state.get('windows', None)
        self._min_change = state.get('min_change', None)
        self._max_q = state.get('max_q', None)
        self._min_change = state.get('min_change', None)
        self.dates = state.get('dates', None)
        self.length = None
        self.average_value = None
        self.average_diff = None

    def extract_q(self, qhat_values):
        """
        Given an ordered sequence of Q-Hat values, output the max value and index

        :param list qhat_values: qhat values
        :return: list (max , index, etc)
        """
        if qhat_values:
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

    # Implementing change-point detection algorithm from https://arxiv.org/pdf/1306.4933.pdf
    def qhat_values(self, series):  #pylint: disable=too-many-locals,too-many-branches
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        length = len(series)
        self.length = length
        if length < 5:
            # Average value and average diff are used even when there is no data to avoid an error.
            self.average_value = 1
            self.average_diff = 1
            return [0] * length
        n = 2
        m = length - n
        qhat_values = [0, 0]  # represents q when n = 0, 1
        # The following line could safely replace the next 6 lines
        # diffs = [[abs(series[i] - series[j]) for i in range(length)] for j in range(length)]
        diffs = [None] * length
        for i in range(length):
            diffs[i] = [0] * length
        for i in range(length):
            for j in range(length):
                diffs[i][j] = abs(series[i] - series[j])

        term1 = 0.0  # sum i:0-n, j:n-t, diffs[i][j]
        term2 = 0.0  # sum i:0-n, k:(i+1)-n, diffs[i][k]
        term3 = 0.0  # sum j:n-length, k:(j+i)-length, diffs[j][k]

        # Normalization constants
        self.average_value = np.average(series)
        # I'm sure there's a better way than this next line, but it works for now
        self.average_diff = np.average(list(itertools.chain(*diffs)))
        # term1 = sum(diffs[i][j] for i in range(n) for j in range(n,length))
        for i in range(n):
            for j in range(n, length):
                term1 += diffs[i][j]
        # term2 = sum(diffs[i][k] for i in range(n) for k in range(i+1,n))
        for i in range(n):
            for k in range((i + 1), n):
                term2 += diffs[i][k]
        # term3 = sum(diffs[j][k] for j in range(n, length) for k in range(j+1,length))
        for j in range(n, length):
            for k in range((j + 1), length):
                term3 += diffs[j][k]

        term1_reg = term1 * (2.0 / (m * n))
        term2_reg = term2 * (2.0 / (n * (n - 1)))
        term3_reg = term3 * (2.0 / (m * (m - 1)))
        newq = (m * n / (m + n)) * (term1_reg - term2_reg - term3_reg)
        qhat_values.append(newq)

        for _ in range(3, (length - 2)):
            n += 1
            m = length - n

            # update term 1
            for y in range(n - 1):
                term1 -= diffs[n - 1][y]
            for y in range(n, length):
                term1 += diffs[y][n - 1]

            # update term 2
            for y in range(n - 1):
                term2 += diffs[n - 1][y]

            # update term 3
            for y in range((n + 1), length):
                term3 -= diffs[y][n]

            term1_reg = term1 * (2.0 / (m * n))
            term2_reg = term2 * (2.0 / (n * (n - 1)))
            term3_reg = term3 * (2.0 / (m * (m - 1)))
            newq = (m * n / (m + n)) * (term1_reg - term2_reg - term3_reg)

            qhat_values.append(newq)

        qhat_values.append(0)
        qhat_values.append(0)
        return qhat_values

    @property
    def change_points(self, seed=1234):
        """
        Property to access change points.
        """
        with deterministic_random(seed):
            return self._compute_change_points()

    def _compute_change_points(self):  #pylint: disable=too-many-locals
        """
        Compute the change points. This is lazy and only runs once.
        """
        if self._change_points is None:
            windows = []
            pts = len(self.series)
            qhat_values = self.qhat_values(self.series)
            LOG.debug("compute_change_points", qs=enumerate(qhat_values))
            first_q = self.extract_q(qhat_values)
            max_q = first_q[1]
            min_change = max_q
            change_points = []

            # HIERARCHICALLY COMPUTE OTHER CHANGEPOINTS
            terminated = False
            while not terminated:
                candidates = []
                windows = [0] + sorted([c[0] for c in change_points]) + [pts]
                for i in range(len(windows) - 1):
                    window = self.series[windows[i]:windows[i + 1]]
                    win_qs = self.qhat_values(window)
                    win_max = self.extract_q(win_qs)
                    win_max[0] += windows[i]

                    candidates.append(win_max)
                candidates.sort(key=lambda tup: tup[1])
                candidate_q = candidates[len(candidates) - 1][1]

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
                    permute_candidates.sort(key=lambda tup: tup[1])
                    permute_q = permute_candidates[len(permute_candidates) - 1][1]
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

    def add_to_change_points(self, change_points, algorithm, keys):
        # pylint: disable=too-many-locals
        """
        Update raw change points to:
            1) Sort the change point indexes.
            2) Use the sorted change point indexes to get the start end ranges.
            3) Use the start / end ranges to create a list of change points including the ranges.
            4) Calculate descriptive stats from series[prev:start] and series[end:next]
            5) Create change point dicts from this data.

        :param list(list) change_points: The raw change points data.
        :param str algorithm: The algorithm name.
        :param list(str) keys: The  names for the values in change_points.

        :return: The change points in order of probability.
        :rtype: list(dict).
        """
        points = []
        sorted_indexes = sorted([point[0] for point in change_points])
        start_ends = generate_start_and_end(sorted_indexes, self.series, weighting=self.weighting)
        link_ordered_change_points(start_ends, self.series)

        for order_of_change_point, point in enumerate(change_points):
            i = next(i for i, start_end in enumerate(start_ends) if point[0] == start_end['index'])
            raw = dict(zip(keys, point))
            index = raw['index']

            point = OrderedDict([('previous', start_ends[i]['previous']),
                                 ('start', start_ends[i]['start']),
                                 ('index', raw['index']),
                                 ('end', start_ends[i]['end']),
                                 ('next', start_ends[i]['next']),
                                 ('location', start_ends[i]['location']),
                                 ('weighting', self.weighting),
                                 ('probability', 1.0 - raw['probability']),
                                 ('revision', self.revisions[index]),
                                 ('create_time', self.orders[index]),
                                 ('thread_level', self.thread_level),
                                 ('order', self.orders[index]),
                                 ('order_of_change_point', order_of_change_point),
                                 ('algorithm_name', algorithm),
                                 ('statistics', start_ends[i].get('statistics', {})),
                                 ('raw', raw)]) # yapf: disable
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

    def render(self, axes=None):  #pylint: disable=too-many-locals
        """
        Plot in matplotlib.
        """
        import matplotlib.pyplot as plt
        flag_new = False
        pts = len(self.series)
        sort_pts = sorted(self.series)
        lowbound = sort_pts[0] * 0.9
        hibound = sort_pts[len(sort_pts) - 1] * 1.1
        xvals = [i for i in range(pts)]

        windows = self.windows
        if windows[len(windows) - 1] - windows[len(windows) - 2] > self.online + 1:
            current_dist = sorted(windows[len(windows) - (self.online + 1):len(windows) - 1])
            new_pt = windows[len(windows) - 1]
            min_end = current_dist[0]
            max_end = current_dist[len(current_dist) - 1]
            if new_pt < min_end or new_pt > max_end:
                flag_new = True

        def format_fn(tick_val, _):
            """
            Helper.
            """
            if int(tick_val) < len(self.revisions):
                i = int(tick_val)
                tick_str = self.revisions[i][0:7]
                if self.dates and i < len(self.dates):
                    tick_str = tick_str + '\n' + self.dates[i].strftime("%H:%M %Y/%m/%d")
            else:
                tick_str = ''
            return tick_str

        title = "{name} ({threads}) : {algorithm}".format(
            name=self.testname, threads=self.threads if self.threads else 'max', algorithm="qhat")

        # always create 1 subplot so that the rest of the code is shared
        if not axes:
            plt.figure(figsize=(DEFAULT_FIGIZE[0], DEFAULT_FIGIZE[1] / 2))
            axes = plt.subplot(1, 1, 1)

        axes.set_title(title, size=16)
        axes.set_ylabel('ops per sec')
        axes.axis([0, pts, lowbound, hibound])

        axes.xaxis.set_major_formatter(FuncFormatter(format_fn))
        axes.xaxis.set_major_locator(MaxNLocator(integer=True))

        for tick in axes.get_xticklabels():
            tick.set_visible(True)

        # DRAW GRAPH
        for change_point in self.change_points:
            # fake probabilities while we investigate
            # p = (change_point[1] - self.min_change) / (self.max_q - self.min_change)
            # print(p)
            # diff to min_value sets color
            diff = (self.max_q - self.min_change)
            if not diff:
                diff = 1
            cval = format(255 - min(255, int(
                (change_point['value'] - self.min_change) / diff * 255)), '02x')
            cstring = '#ff' + cval + cval
            axes.axvline(x=change_point['index'], color=cstring, label=change_point['revision'])
        if flag_new and self.series:
            axes.axvline(x=pts - 1, color='r', linewidth=2, label=self.revisions[pts - 1])

        axes.plot(xvals, self.series, 'b-')
        axes.legend(loc="upper right")
        return plt

    def save(self, _):
        """
        Save.
        """
        self.state['change_points'] = self.change_points
        self.state['windows'] = self.windows
        self.state['online'] = self.online
        self.state['min_change'] = self.min_change
        self.state['max_q'] = self.max_q
        self.state['min_change'] = self.min_change
        # TODO: encapsulate
