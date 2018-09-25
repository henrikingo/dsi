"""
Group of functionality to compare performance of various implementations.

The implementations in this file are fixed. They should be considered old or suspect.
For the current version, see signal_processing.qhat.QHat.

In addition, they are grouped in a single file so that a cython version can be created by
simply copying this file to a new file with a pyx extension.

The only current exception to this pattern are the Windowed implementations, which should be
considered suspect as they are in development.
"""
from __future__ import print_function

import numpy as np
import structlog

import signal_processing.qhat
import signal_processing.native.qhat

LOG = structlog.getLogger(__name__)


class OriginalQHat(object):
    """
    Original O(n^2) with comprehensions.
    """

    def __init__(self):
        self.average_value = 0
        self.average_diff = 0
        self.window = 0

    # Implementing change-point detection algorithm from https://arxiv.org/pdf/1306.4933.pdf
    def qhat_values(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        self.window = len(series)
        qhat_values = np.zeros(len(series), dtype=np.float)
        if self.window < 5:
            # Average value and average diff are used even when there is no data.
            # This avoids an error.
            self.average_value = 1
            self.average_diff = 1
            return qhat_values

        diffs = signal_processing.qhat.QHat.calculate_diffs(series)

        # Normalization constants
        self.average_value = np.average(series)
        self.average_diff = np.average(diffs)

        for n in range(2, self.window - 2):
            m = self.window - n
            term1 = sum(diffs[i][j] for i in range(n) for j in range(n, self.window))
            term2 = sum(diffs[i][k] for i in range(n) for k in range(i + 1, n))
            term3 = sum(
                diffs[j][k] for j in range(n, self.window) for k in range(j + 1, self.window))

            qhat_values[n] = signal_processing.qhat.QHat.calculate_q(term1, term2, term3, m, n)

        return qhat_values


class NumpyQHat(object):
    """
    Numpy O(n^2) implementation.
    """

    def __init__(self):
        self.average_value = 0
        self.average_diff = 0
        self.window = 0

    def qhat_values(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        self.window = len(series)
        qhat_values = np.zeros(len(series), dtype=np.float)
        if self.window < 5:
            # Average value and average diff are used even when there is no data.
            # This avoids an error.
            self.average_value = 1
            self.average_diff = 1
            return qhat_values
        diffs = signal_processing.qhat.QHat.calculate_diffs(series)

        self.average_value = np.average(series)
        self.average_diff = np.average(diffs)

        for n in range(2, self.window - 2):
            m = self.window - n

            term1 = np.sum(diffs[:n, n:])
            term2 = np.sum(np.triu(diffs[:n, :n], 0))
            term3 = np.sum(np.triu(diffs[n:, n + 1:], 0))

            qhat_values[n] = signal_processing.qhat.QHat.calculate_q(term1, term2, term3, m, n)
        return qhat_values


class OptimizedQHat(object):
    """
    Optimized implementation O(n).
    """

    def __init__(self):
        self.average_value = 0
        self.average_diff = 0
        self.window = 0

    def qhat_values(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        self.window = len(series)
        qhat_values = np.zeros(self.window, dtype=np.float)
        if self.window < 5:
            # Average value and average diff are used even when there is no data.
            # This avoids an error.
            self.average_value = 1
            self.average_diff = 1
            return qhat_values
        diffs = signal_processing.qhat.QHat.calculate_diffs(series)

        self.average_value = np.average(series)
        self.average_diff = np.average(diffs)

        n = 2
        m = self.window - n

        term1 = sum(diffs[i][j] for i in range(n) for j in range(n, self.window))
        term2 = sum(diffs[i][k] for i in range(n) for k in range(i + 1, n))
        term3 = sum(diffs[j][k] for j in range(n, self.window) for k in range(j + 1, self.window))

        qhat_values[n] = signal_processing.qhat.QHat.calculate_q(term1, term2, term3, m, n)

        for n in range(3, (self.window - 2)):
            m = self.window - n
            # update term 1
            row_delta = sum(diffs[n - 1][y] for y in range(n - 1))
            column_delta = sum(diffs[y][n - 1] for y in range(n, self.window))

            term1 = term1 - row_delta + column_delta
            term2 = term2 + row_delta
            term3 = term3 - column_delta

            qhat_values[n] = signal_processing.qhat.QHat.calculate_q(term1, term2, term3, m, n)

        return qhat_values


class NumpyOptimizedQHat(object):
    """
    Optimized calculation in numpy.
    """

    def __init__(self):
        self.average_value = 0
        self.average_diff = 0
        self.window = 0

    def qhat_values(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        self.window = len(series)
        qhat_values = np.zeros(self.window, dtype=np.float)
        if self.window < 5:
            # Average value and average diff are used even when there is no data.
            # This avoids an error.
            self.average_value = 1
            self.average_diff = 1
            return qhat_values
        diffs = signal_processing.qhat.QHat.calculate_diffs(series)

        self.average_value = np.average(series)
        self.average_diff = np.average(diffs)

        n = 2
        m = self.window - n

        term1 = np.sum(diffs[:n, n:])
        term2 = np.sum(np.triu(diffs[:n, :n], 0))
        term3 = np.sum(np.triu(diffs[n:, n + 1:], 0))

        qhat_values[n] = signal_processing.qhat.QHat.calculate_q(term1, term2, term3, m, n)

        for n in range(3, (self.window - 2)):
            m = self.window - n
            row_delta = np.sum(diffs[n - 1, :n - 1])
            column_delta = np.sum(diffs[n:, n - 1])

            term1 = term1 - row_delta + column_delta
            term2 = term2 + row_delta
            term3 = term3 - column_delta

            qhat_values[n] = signal_processing.qhat.QHat.calculate_q(term1, term2, term3, m, n)

        return qhat_values


class WindowedQHat(object):
    """
    QHat O(window^2) with implementation.
    Implements an un-optimized / un-tested 'straight' python
    version of in PERF-1669.
    """

    def __init__(self):
        self.average_value = 0
        self.average_diff = 0
        self.window = 0

    # Implementing change-point detection algorithm from https://arxiv.org/pdf/1306.4933.pdf
    def qhat_values(self, series, window):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        self.window = len(series)
        qhat_values = np.zeros(len(series), dtype=np.float)
        if self.window < 5:
            # Average value and average diff are used even when there is no data.
            # This avoids an error.
            self.average_value = 1
            self.average_diff = 1
            return qhat_values

        diffs = signal_processing.qhat.QHat.calculate_diffs(series)

        # Normalization constants
        self.average_value = np.average(series)
        self.average_diff = np.average(diffs)

        for n in range(2, self.window - 2):
            m = self.window - n

            term1 = sum(diffs[i][j]
                        for i in range(max(0, n - window + 1), n)
                        for j in range(n, min(self.window, n + window)))
            term2 = sum(
                diffs[i][k] for i in range(max(0, n - window + 1), n) for k in range((i + 1), n))
            term3 = sum(diffs[j][k]
                        for j in range(n, min(self.window, n + window + 1))
                        for k in range((j + 1), min(self.window, n + window + 1)))

            qhat_values[n] = signal_processing.qhat.QHat.calculate_q(term1, term2, term3, m, n)
        return qhat_values


# The following classes implement an un-optimized / un-tested version described in
# PERF-1669.
class NumpyWindowedQHat(object):
    """
    Numpy O(window^2) implementation.
    Implements an un-optimized / un-tested numpy
    version of in PERF-1669.
    """

    def __init__(self):
        self.average_value = 0
        self.average_diff = 0
        self.window = 0

    def qhat_values(self, series, window):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """
        self.window = len(series)
        qhat_values = np.zeros(len(series), dtype=np.float)
        if self.window < 5:
            # Average value and average diff are used even when there is no data.
            # This avoids an error.
            self.average_value = 1
            self.average_diff = 1
            return qhat_values
        diffs = signal_processing.qhat.QHat.calculate_diffs(series)

        self.average_value = np.average(series)
        self.average_diff = np.average(diffs)

        window = int(round(self.window / 2))

        for n in range(2, self.window - 2):
            m = self.window - n

            term1 = np.sum(diffs[max(0, n - window + 1):n, n:min(self.window, n + window)])

            row = max(n - window + 1, 0)
            column = row + min(window - 2 + 1, n)
            term2 = np.sum(np.triu(diffs[row:column, row:column], 1))

            term3 = np.sum(np.triu(diffs[n:window + n + 1, n:window + n + 1], 1))

            qhat_values[n] = signal_processing.qhat.QHat.calculate_q(term1, term2, term3, m, n)
        return qhat_values


class NativeQHat(object):
    """
    QHat native optimized implementation.
    """

    def __init__(self):
        self.average_value = 0
        self.average_diff = 0
        self.window = 0

    def qhat_values(self, series):
        """
        Find Q-Hat values for all candidate change points

        :param list series: the points to process
        :return:
        """

        diffs = signal_processing.native.qhat.qhat_diffs_wrapper(series)
        qhat_values = np.zeros(len(series), dtype=np.float)
        signal_processing.native.qhat.qhat_values_wrapper(series, diffs, qhat_values)
        return qhat_values
