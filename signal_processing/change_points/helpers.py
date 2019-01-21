"""
change point utility functions.
"""
from collections import OrderedDict

import pymongo
import structlog

LOG = structlog.getLogger(__name__)


def _translate_indexes(change_points_indexes, length):
    """
    Translate and deduplicate change point indexes, preserving order.

    :param list(int) change_points_indexes: The list of change point indexes.
    :param int length: The number of *change points*.
    :return: The list of translated ordered points.
    :rtype: list(int)
    """
    valid_indexes = [
        index for index in change_points_indexes
        if (0 <= index <= length) or (0 > index >= -length - 1)
    ]
    valid_indexes = [index if index >= 0 else length + index + 1 for index in valid_indexes]
    valid_indexes = OrderedDict([(index, index) for index in valid_indexes])
    valid_indexes = valid_indexes.values()
    return valid_indexes


def _generate_all_change_point_ranges(full_series, change_points):
    """
    Generate the ranges for all change points.

    :param dict full_series: The time series data.
    :param list(dict) change_points: The change points.
    :return: The start and end indexes for the change points.
    :rtype: (int, int).
    """
    start = full_series['orders'][0]
    if change_points:
        for change_point in change_points:
            end = change_point['order']
            yield (start, end)
            start = end
    # yield from the last change point to the end of the time series
    yield (start, full_series['orders'][-1])


def _generate_change_point_ranges_from_indexes(full_series, change_points, indexes):
    """
    Generate the ranges for all change points.

    :param dict full_series: The time series data.
    :param list(dict) change_points: The change points.
    :param list(int) indexes: The list of valid translated indexes.
    :return: The start and end indexes for the change points.
    :rtype: (int, int).
    """
    length = len(change_points)
    if not change_points:
        for _ in indexes:
            yield (full_series['orders'][0], full_series['orders'][-1])
    else:
        for index in indexes:
            if index == 0:
                start = full_series['orders'][0]
                end = change_points[index]['order']
            else:
                start = change_points[index - 1]['order']
                if index > length - 1:
                    end = full_series['orders'][-1]
                else:
                    end = change_points[index]['order']
            yield (start, end)


def generate_change_point_ranges(test_identifier, model, change_points_indexes):
    """
    Generate the start and end indexes for each change point.

    Indexing behaves like python indexing so a[len(a) - 1] == a[-1].

    If there are 3 change points, there are actually 4 change point ranges. The 'extra' range
    represents the range from the start of the time series to the first change point.

    For example, with the following series:

    Change Points:        3     6     9
    Indexes:        0 1 2 3 4 5 6 7 8 9 10 11


    The change point ranges are (0,3), (3,6), (6,9), (9, 11).
        (0,3)  is accessed at index 0 or -4
        (3,6)  is accessed at index 1 or -3
        (6,9)  is accessed at index 2 or -2
        (9,11) is accessed at index 3 or -1

    :param dict test_identifier: The project, variant, task, test identifier.
    :param PointsModel model: The replay model.
    :param list change_points_indexes: The change point indexes.
    :return: The start and end indexes for the change points.
    :rtype: (int, int).
    """
    LOG.debug('Loaded change points', test_identifier=test_identifier)

    change_points = list(model.db['change_points'].find(test_identifier).sort(
        [('order', pymongo.ASCENDING)]))
    LOG.debug('Loaded change points', change_points=change_points)

    # exit early if no time series data
    full_series = model.get_points(test_identifier, 0)
    if not full_series['orders']:
        return

    length = len(change_points)

    # exit early if time series data, no change points and no valid indexes
    valid_indexes = _translate_indexes(change_points_indexes, length)
    if change_points_indexes and not valid_indexes and not change_points:
        return

    if change_points_indexes:
        generator = _generate_change_point_ranges_from_indexes(full_series, change_points,
                                                               valid_indexes)
    else:
        generator = _generate_all_change_point_ranges(full_series, change_points)
    for start, end in generator:
        yield start, end
