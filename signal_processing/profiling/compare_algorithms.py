"""
Group of functionality to compare performance of various implementations.

The implementations in this file are fixed. They should be considered old or suspect.
For the current version, see signal_processing.change_points.e_divisive.EDivisive.

In addition, they are grouped in a single file so that a cython version can be created by
simply copying this file to a new file with a pyx extension.

The only current exception to this pattern are the Windowed implementations, which should be
considered suspect as they are in development.
"""
from __future__ import print_function

import numpy as np
import structlog

from signal_processing.change_points.e_divisive import EDivisive
import signal_processing.native.e_divisive

LOG = structlog.getLogger(__name__)


class OriginalEDivisive(object):
    """
    Original O(n^2) with comprehensions.
    """

    # Implementing change-point detection algorithm from https://arxiv.org/pdf/1306.4933.pdf
    def qhat_values(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        length = len(series)
        qhat_values = np.zeros(len(series), dtype=np.float)
        if length < 5:
            return qhat_values

        diffs = EDivisive.calculate_diffs(series)

        for n in range(2, length - 2):
            m = length - n
            term1 = sum(diffs[i][j] for i in range(n) for j in range(n, length))
            term2 = sum(diffs[i][k] for i in range(n) for k in range(i + 1, n))
            term3 = sum(diffs[j][k] for j in range(n, length) for k in range(j + 1, length))

            qhat_values[n] = EDivisive.calculate_q(term1, term2, term3, m, n)

        return qhat_values


class NumpyEDivisive(object):
    """
    Numpy O(n^2) implementation.
    """

    def qhat_values(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        length = len(series)
        qhat_values = np.zeros(len(series), dtype=np.float)
        if length < 5:
            return qhat_values
        diffs = EDivisive.calculate_diffs(series)

        for n in range(2, length - 2):
            m = length - n

            term1 = np.sum(diffs[:n, n:])
            term2 = np.sum(np.triu(diffs[:n, :n], 0))
            term3 = np.sum(np.triu(diffs[n:, n + 1:], 0))

            qhat_values[n] = EDivisive.calculate_q(term1, term2, term3, m, n)
        return qhat_values


class OptimizedEDivisive(object):
    """
    Optimized implementation O(n).
    """

    def qhat_values(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        length = len(series)
        qhat_values = np.zeros(length, dtype=np.float)
        if length < 5:
            return qhat_values
        diffs = EDivisive.calculate_diffs(series)

        n = 2
        m = length - n

        term1 = sum(diffs[i][j] for i in range(n) for j in range(n, length))
        term2 = sum(diffs[i][k] for i in range(n) for k in range(i + 1, n))
        term3 = sum(diffs[j][k] for j in range(n, length) for k in range(j + 1, length))

        qhat_values[n] = EDivisive.calculate_q(term1, term2, term3, m, n)

        for n in range(3, (length - 2)):
            m = length - n
            # update term 1
            row_delta = sum(diffs[n - 1][y] for y in range(n - 1))
            column_delta = sum(diffs[y][n - 1] for y in range(n, length))

            term1 = term1 - row_delta + column_delta
            term2 = term2 + row_delta
            term3 = term3 - column_delta

            qhat_values[n] = EDivisive.calculate_q(term1, term2, term3, m, n)

        return qhat_values


class NumpyOptimizedEDivisive(object):
    """
    Optimized calculation in numpy.
    """

    def qhat_values(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        length = len(series)
        qhat_values = np.zeros(length, dtype=np.float)
        if length < 5:
            return qhat_values
        diffs = EDivisive.calculate_diffs(series)

        n = 2
        m = length - n

        term1 = np.sum(diffs[:n, n:])
        term2 = np.sum(np.triu(diffs[:n, :n], 0))
        term3 = np.sum(np.triu(diffs[n:, n + 1:], 0))

        qhat_values[n] = EDivisive.calculate_q(term1, term2, term3, m, n)

        for n in range(3, (length - 2)):
            m = length - n
            row_delta = np.sum(diffs[n - 1, :n - 1])
            column_delta = np.sum(diffs[n:, n - 1])

            term1 = term1 - row_delta + column_delta
            term2 = term2 + row_delta
            term3 = term3 - column_delta

            qhat_values[n] = EDivisive.calculate_q(term1, term2, term3, m, n)

        return qhat_values


class WindowedEDivisive(object):
    """
    E-Divisive O(window^2) with implementation.
    Implements an un-optimized / un-tested 'straight' python
    version of in PERF-1669.
    """

    # Implementing change-point detection algorithm from https://arxiv.org/pdf/1306.4933.pdf
    def qhat_values(self, series, window):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        length = len(series)
        qhat_values = np.zeros(len(series), dtype=np.float)
        if length < 5:
            return qhat_values

        diffs = EDivisive.calculate_diffs(series)

        for n in range(2, length - 2):
            m = length - n

            term1 = sum(diffs[i][j]
                        for i in range(max(0, n - window + 1), n)
                        for j in range(n, min(length, n + window)))
            term2 = sum(
                diffs[i][k] for i in range(max(0, n - window + 1), n) for k in range((i + 1), n))
            term3 = sum(diffs[j][k]
                        for j in range(n, min(length, n + window + 1))
                        for k in range((j + 1), min(length, n + window + 1)))

            qhat_values[n] = EDivisive.calculate_q(term1, term2, term3, m, n)
        return qhat_values


# The following classes implement an un-optimized / un-tested version described in
# PERF-1669.
class NumpyWindowedEDivisive(object):
    """
    Numpy O(window^2) implementation.
    Implements an un-optimized / un-tested numpy
    version of in PERF-1669.
    """

    def qhat_values(self, series, window):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        length = len(series)
        qhat_values = np.zeros(len(series), dtype=np.float)
        if length < 5:
            return qhat_values
        diffs = EDivisive.calculate_diffs(series)

        window = int(round(length / 2))

        for n in range(2, length - 2):
            m = length - n

            term1 = np.sum(diffs[max(0, n - window + 1):n, n:min(length, n + window)])

            row = max(n - window + 1, 0)
            column = row + min(window - 2 + 1, n)
            term2 = np.sum(np.triu(diffs[row:column, row:column], 1))

            term3 = np.sum(np.triu(diffs[n:window + n + 1, n:window + n + 1], 1))

            qhat_values[n] = EDivisive.calculate_q(term1, term2, term3, m, n)
        return qhat_values


class NativeEDivisive(object):
    """
    E-Divisive native optimized implementation.
    """

    def qhat_values(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """

        diffs = signal_processing.native.e_divisive.qhat_diffs_wrapper(series)
        qhat_values = np.zeros(len(series), dtype=np.float)
        signal_processing.native.e_divisive.qhat_values_wrapper(series, diffs, qhat_values)
        return qhat_values
