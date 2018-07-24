"""
QHat describe stats related tests.
"""
import unittest

import numpy as np

from bin.common.log import setup_logging

from signal_processing.qhat import describe_change_point
from sp_utils import approx_dict

setup_logging(False)


class TestDescribeChangePoints(unittest.TestCase):
    """
    Test generate_pairs.
    """

    def test_empty(self):
        """
        Test empty array.
        """
        expected = {}
        change_point = {'previous': 0, 'start': 0, 'end': 0, 'next': 0}

        description = describe_change_point(change_point, range(0), {})
        self.assertEqual(description, expected)

    def test_start_empty(self):
        """
        Test start empty array.
        """
        expected = {'next': dict(nobs=1, minmax=(0, 0), mean=0.0, skewness=0.0, kurtosis=-3.0)}
        change_point = {'previous': 0, 'start': 0, 'end': 0, 'next': 1}

        description = describe_change_point(change_point, range(1), {})
        self.assertEqual(len(expected), len(description))
        to_next = description['next']
        self.assertDictContainsSubset(expected['next'], to_next)
        self.assertTrue(np.isnan(to_next['variance']))

    def test_end_empty(self):
        """
        Test end empty array.
        """
        expected = {'previous': dict(nobs=1, minmax=(0, 0), mean=0.0, skewness=0.0, kurtosis=-3.0)}
        change_point = {'previous': 0, 'start': 1, 'end': 1, 'next': 1}

        description = describe_change_point(change_point, range(1), {})
        self.assertEqual(len(expected), len(description))
        from_previous = description['previous']
        self.assertDictContainsSubset(expected['previous'], from_previous)
        self.assertTrue(np.isnan(from_previous['variance']))

    def test_start_and_end_1(self):
        """
        Test start and end.
        """
        expected = {
            'previous': dict(nobs=1, minmax=(0, 0), mean=0.0, skewness=0.0, kurtosis=-3.0),
            'next': dict(nobs=1, minmax=(1, 1), mean=1.0, skewness=0.0, kurtosis=-3.0)
        }
        change_point = {'previous': 0, 'start': 1, 'end': 1, 'next': 2}

        description = describe_change_point(change_point, range(2), {})
        self.assertEqual(len(expected), len(description))
        from_previous = description['previous']
        self.assertDictContainsSubset(expected['previous'], from_previous)
        self.assertTrue(np.isnan(from_previous['variance']))

        to_next = description['next']
        self.assertDictContainsSubset(expected['next'], to_next)
        self.assertTrue(np.isnan(to_next['variance']))

    def test_start_and_end_2(self):
        """
        Test another start and end.
        """
        expected = {
            'previous':
                dict(nobs=5, minmax=(0, 4), mean=2.0, variance=2.5, skewness=0.0, kurtosis=-1.3),
            'next':
                dict(nobs=9, minmax=(6, 14), mean=10.0, variance=7.5, skewness=0.0, kurtosis=-1.23)
        }
        change_point = {'previous': 0, 'start': 5, 'end': 6, 'next': 15}

        description = describe_change_point(change_point, range(15), {})
        self.assertEqual(len(expected), len(description))
        from_previous = description['previous']
        self.assertDictContainsSubset(approx_dict(expected['previous']), approx_dict(from_previous))

        to_next = description['next']
        self.assertDictContainsSubset(approx_dict(expected['next']), approx_dict(to_next))
