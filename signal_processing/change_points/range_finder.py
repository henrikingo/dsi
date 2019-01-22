"""
Manipulation of points ranges.
"""
import itertools

import numpy as np
from scipy import stats
import structlog

from signal_processing.change_points.weights import exponential_weights

LOG = structlog.getLogger(__name__)

_LOCATION_BEHIND = 'behind'
"""
The location refers to whether we need to search forward in history from the candidate commit, or
backwards.
See :method:`get_location` for more details.
"""

_LOCATION_AHEAD = 'ahead'
"""
The location refers to whether we need to search forward in history from the candidate commit, or
backwards.
See :method:`get_location` for more details.
"""


def _get_location(behind_average, value, ahead_average):
    """
    The change point reported by E-Divisive is often not going to be the exact commit that
    introduced the change, in part because we don't run on every commit. We need to search for
    (and run) the commit that introduced the change.

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
        location = _LOCATION_AHEAD
    else:
        location = _LOCATION_BEHIND

    LOG.debug("calc location", location=location)
    return location


def _select_start_end(input_series, prev_index, index, next_index, weighting, bounds=1):
    # pylint: disable=too-many-arguments, too-many-locals, too-many-branches
    """
    To state it simply, we want to find the index that is furthest away from the desired mean line
    (the one that has the greatest difference to value) but which is as close as possible to index
    (as this point has been chosen by E-Divisive).

    The change point reported by E-Divisive is often not going to be the exact commit that
    introduced the change, in part because we don't run on every commit. We need to search for
    (and run) the commit that introduced the change. The location refers to the need to search ahead
    in history from the candidate commit, or behind.

    This method selects a start and end index that encompasses the actual change point.

    The steps involved are:
    1) Determine the general location, behind for when the change point is less than index or
    ahead when it is greater of index.

    2) Create a multiplier based on the bounds and the weighting (so as to prefer closer
    points). Growth or decay in the values based the location and the distance from value. The
    weights are generated to give more consideration to points closer to the chosen E-Divisive
    index.

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
        return next_index, next_index, _LOCATION_AHEAD

    series = np.array(input_series, dtype=np.float64)
    value = series[index]

    # Calculate the averages.
    behind_average = np.mean(series[prev_index:index - 1])
    ahead_average = np.mean(series[index + 1:next_index])

    if behind_average == ahead_average:
        LOG.debug("behind and ahead averages are the same", behind_average=behind_average)
        return index, index, _LOCATION_AHEAD

    if np.isnan(ahead_average):
        ahead_average = series[index]
        location = _LOCATION_BEHIND
        LOG.debug("nan", location=location)
    elif np.isnan(behind_average):
        behind_average = series[index]
        location = _LOCATION_AHEAD
        LOG.debug("nan", location=location)
    else:
        # Get the location (ahead or behind).
        location = _get_location(behind_average, value, ahead_average)
    LOG.debug("selected", location=location)

    # Set the start and end indexes, ensuring we don't overshoot.
    if location == _LOCATION_BEHIND:
        start = max(index - bounds + 1, prev_index)
        end = index + 1
    else:
        start = index
        end = min(index + bounds, next_index)

    # Create our weightings, these values cause this code to prefer indexes closer to the
    # selection made by the algorithm. No reverse on np.array, so flip the the values where
    # appropriate for growth or decay. Flip may return a copy or a view.
    weights = exponential_weights(end - start, weighting)
    if location == _LOCATION_AHEAD:
        weights = np.flip(weights, 0)

    # Get the correct range and subtract the correct average.
    points = series[start:end]
    if location == _LOCATION_AHEAD:
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
    """
    start_ends = []
    if sorted_change_points:
        prev_index = 0
        for position, point in enumerate(sorted_change_points):
            if position + 1 < len(sorted_change_points):
                next_index = sorted_change_points[position + 1]
            else:
                next_index = len(series)

            start, end, location = _select_start_end(
                series, prev_index, point, next_index, weighting=weighting)

            start_ends.append({'index': point, 'start': start, 'end': end, 'location': location})
            prev_index = end

    return start_ends


def _generate_pairs(values):
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
        for current_change_point, next_change_points in _generate_pairs(sorted_change_points):
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
