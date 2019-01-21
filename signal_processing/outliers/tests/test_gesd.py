# -*- coding: utf-8 -*-
"""
Unit tests for signal_processing/outliers/gesd.py.
"""
import os
import random
import unittest

import numpy as np
from test_lib.fixture_files import FixtureFiles

from signal_processing.outliers.gesd import gesd
from signal_processing.change_points.qhat import deterministic_random


class TestGesdInputs(unittest.TestCase):
    """ Test error handling. """

    def test_no_data(self):
        """Test no data."""
        self.assertRaisesRegexp(ValueError, r'No Data', gesd, None)
        self.assertRaisesRegexp(ValueError, r'No Data', gesd, [])

    def test_max_outliers(self):
        """Test insufficient data."""
        self.assertRaisesRegexp(ValueError, r'max_outliers.* must be >= 1', gesd, [1], 0)
        self.assertRaisesRegexp(ValueError, r'max_outliers.* must be >= 1', gesd, [1], -1)

    def test_insufficient_data(self):
        """Test insufficient data."""
        self.assertRaisesRegexp(ValueError, r'max_outliers.* <= length', gesd, [1])
        self.assertRaisesRegexp(ValueError, r'max_outliers.* <= length', gesd, [1] * 10)

    def test_significance_level_zero(self):
        """Test invalid significance_level."""
        self.assertRaisesRegexp(
            ValueError, r'invalid significance_level', gesd, [1] * 20, significance_level=0)

    def test_significance_level_lt_zero(self):
        """Test invalid significance_level."""
        self.assertRaisesRegexp(
            ValueError, r'invalid significance_level', gesd, [1] * 20, significance_level=-1)

    def test_significance_level_gt_one(self):
        """Test invalid significance_level."""
        self.assertRaisesRegexp(
            ValueError, r'invalid significance_level', gesd, [1] * 20, significance_level=1)


class TestSimple(unittest.TestCase):
    """ Test Simple data. """

    def test_flat(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd([1] * 20)
        self.assertEquals(0, number_outliers)
        self.assertEquals([], suspicious_indexes)
        self.assertEquals([], test_statistics)
        self.assertEquals([], critical_values)
        self.assertEquals([], all_z_scores)

    def test_mad_flat(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd([1] * 20, mad=True)
        self.assertEquals(0, number_outliers)
        self.assertEquals([], suspicious_indexes)
        self.assertEquals([], test_statistics)
        self.assertEquals([], critical_values)
        self.assertEquals([], all_z_scores)


FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


class TestReal(unittest.TestCase):
    """ Test Real data. """

    def _test(self, test_file='standard'):
        """ test helper."""
        file_parts = [
            'sys-perf', 'linux-1-node-replSet', 'bestbuy_query', 'canary_client-cpuloop-10x', '1'
        ] + ['{}.json'.format(test_file)]

        filename = os.path.join(*file_parts)
        fixtures = FIXTURE_FILES.load_json_file(filename)
        start_order = fixtures['data']['start_order']
        end_order = fixtures['data']['end_order']

        full_series = fixtures['data']['time_series']
        orders = full_series['orders']
        series = np.array(
            full_series['series'][orders.index(start_order):orders.index(end_order)], dtype=float)

        expected = fixtures['expected']

        number_outliers, suspicious_indexes, _, _, _ = \
            gesd(series, mad=fixtures['data'].get('mad', False))

        self.assertEquals(expected['number_outliers'], number_outliers)
        self.assertListEqual(expected['suspicious_indexes'], suspicious_indexes)

    def test_standard(self):
        """Test gesd on real data with standard."""

        self._test()

    def test_mad(self):
        """Test gesd on real data with Median Absolute Deviation."""

        self._test('mad')


class TestTIG1372(unittest.TestCase):
    """ Test Simple data. """

    def setUp(self):
        self.series = [-1] * 203 + [-2] + [-1] * 75

    def test_standard(self):
        """Test gesd on almost flat data."""
        number_outliers, suspicious_indexes, _, _, _ = gesd(self.series)
        self.assertEquals(1, number_outliers)
        self.assertEquals([203], suspicious_indexes)

    def test_mad(self):
        """Test gesd on almost flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(self.series, mad=True)
        self.assertEquals(0, number_outliers)
        self.assertEquals([], suspicious_indexes)
        self.assertEquals([], test_statistics)
        self.assertEquals([], critical_values)
        self.assertEquals([], all_z_scores)


FIRST_OUTLIER = 700
SECOND_OUTLIER = 100
THIRD_OUTLIER = 5
with deterministic_random(3.1415):
    SINGLE = [FIRST_OUTLIER if i == 7 else random.uniform(0, 1) for i in range(15)]
    DOUBLE = SINGLE + [SECOND_OUTLIER if i == 5 else random.uniform(0, 1) for i in range(10)]
    TRIPLE = DOUBLE + [THIRD_OUTLIER if i == 5 else random.uniform(0, 1) for i in range(10)]


class TestMeanOutliers(unittest.TestCase):
    """ Test standard z score. """

    # pylint: disable=unused-variable
    def test_single(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(SINGLE, max_outliers=1)
        self.assertEquals(1, number_outliers)
        self.assertEquals([7], suspicious_indexes)

    def test_single_max_10(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(SINGLE)
        self.assertEquals(1, number_outliers)
        self.assertEquals(7, suspicious_indexes[0])

    def test_double(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(DOUBLE, max_outliers=2)
        self.assertEquals(2, number_outliers)
        self.assertEquals([7, 20], suspicious_indexes)

    def test_double_max_10(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(DOUBLE)
        self.assertEquals(2, number_outliers)
        self.assertEquals(7, suspicious_indexes[0])
        self.assertEquals(20, suspicious_indexes[1])

    def test_triple(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(TRIPLE, max_outliers=3)
        self.assertEquals(3, number_outliers)
        self.assertEquals([7, 20, 30], suspicious_indexes)

    def test_triple_max_2(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(TRIPLE, max_outliers=2)
        self.assertEquals(2, number_outliers)
        self.assertEquals([7, 20], suspicious_indexes)

    def test_triple_max_10(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(TRIPLE)
        self.assertEquals(3, number_outliers)
        self.assertEquals([7, 20, 30], suspicious_indexes[:3])


class TestMedianOutlier(unittest.TestCase):
    """ Test Median Absolute Deviation. """

    # pylint: disable=unused-variable
    def test_single(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(SINGLE, max_outliers=1, mad=True)
        self.assertEquals(1, number_outliers)
        self.assertEquals([7], suspicious_indexes)

    def test_single_max_10(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(SINGLE, mad=True)
        self.assertEquals(10, number_outliers)
        self.assertEquals(7, suspicious_indexes[0])

    def test_double(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(DOUBLE, max_outliers=2)
        self.assertEquals(2, number_outliers)
        self.assertEquals([7, 20], suspicious_indexes)

    def test_double_max_10(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(DOUBLE, max_outliers=2, mad=True)
        self.assertEquals(2, number_outliers)
        self.assertEquals([7, 20], suspicious_indexes)

    def test_triple(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(TRIPLE, max_outliers=3, mad=True)
        self.assertEquals(3, number_outliers)
        self.assertEquals([7, 20, 30], suspicious_indexes)

    def test_triple_max_2(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(TRIPLE, max_outliers=2, mad=True)
        self.assertEquals(2, number_outliers)
        self.assertEquals([7, 20], suspicious_indexes)

    def test_triple_max_10(self):
        """Test gesd on flat data."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(TRIPLE, mad=True)
        self.assertEquals(3, number_outliers)
        self.assertEquals([7, 20, 30], suspicious_indexes[:3])


class TestCanonical(unittest.TestCase):
    """ Test canonical example from
https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h3.htm#Generalized%20ESD%20Test%20Example.

  H0:  there are no outliers in the data
  Ha:  there are up to 10 outliers in the data

  Significance level:  α = 0.05
  Critical region:  Reject H0 if Ri > critical value

  Summary Table for Two-Tailed Test
  ---------------------------------------
        Exact           Test     Critical
    Number of      Statistic    Value, λi
  Outliers, i      Value, Ri          5 %
  ---------------------------------------
          1          3.118          3.158
          2          2.942          3.151
          3          3.179          3.143 *
          4          2.810          3.136
          5          2.815          3.128
          6          2.848          3.120
          7          2.279          3.111
          8          2.310          3.103
          9          2.101          3.094
         10          2.067          3.085
     """
    # pylint: disable=unused-variable

    ROSNER = [
        -0.25, 0.68, 0.94, 1.15, 1.20, 1.26, 1.26, 1.34, 1.38, 1.43, 1.49, 1.49, 1.55, 1.56, 1.58,
        1.65, 1.69, 1.70, 1.76, 1.77, 1.81, 1.91, 1.94, 1.96, 1.99, 2.06, 2.09, 2.10, 2.14, 2.15,
        2.23, 2.24, 2.26, 2.35, 2.37, 2.40, 2.47, 2.54, 2.62, 2.64, 2.90, 2.92, 2.92, 2.93, 3.21,
        3.26, 3.30, 3.59, 3.68, 4.30, 4.64, 5.34, 5.42, 6.01
    ]

    CANONICAL_STATS = [3.118, 2.942, 3.179, 2.810, 2.815, 2.848, 2.279, 2.310, 2.101, 2.067]
    CANONICAL_CRITICAL = [3.158, 3.151, 3.143, 3.136, 3.128, 3.120, 3.111, 3.103, 3.094, 3.085]
    CANONICAL_INDEXES = [53, 52, 51, 50, 0, 49, 48, 47, 1, 46]

    def test_canonical(self):
        """Test gesd implementation."""
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(self.ROSNER)

        self.assertEquals(3, number_outliers)
        self.assertTrue(np.array_equal(suspicious_indexes, self.CANONICAL_INDEXES))

        self.assertTrue(all(np.isclose(self.CANONICAL_STATS, np.fabs(test_statistics), rtol=.001)))
        self.assertTrue(all(np.isclose(self.CANONICAL_CRITICAL, critical_values, rtol=.001)))

    def test_mad(self):
        """ Test MAD z score. """
        number_outliers, suspicious_indexes, test_statistics, critical_values, all_z_scores =\
            gesd(self.ROSNER, mad=True)

        self.assertEquals(4, number_outliers)
        self.assertTrue(
            np.array_equal(suspicious_indexes[:number_outliers],
                           self.CANONICAL_INDEXES[:number_outliers]))
