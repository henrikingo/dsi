"""
E-Divisive related tests.
"""
import unittest

from mock import MagicMock
import numpy as np

from bin.common.log import setup_logging
from signal_processing.change_points.e_divisive import EDivisive

setup_logging(False)

EMPTY_NP_ARRAY = np.array([], dtype=np.float)


class TestEDivisive(unittest.TestCase):
    """
    Test for EDivisive class methods.
    """

    def test_series_none(self):
        """
        Test that compute_change_points parameters are validated.
        """
        e_divisive = EDivisive()
        e_divisive._compute_change_points = MagicMock()

        e_divisive.compute_change_points(None)

        series_arg = e_divisive._compute_change_points.call_args[0][0]
        self.assertIsInstance(series_arg, np.ndarray)
        self.assertEqual(series_arg.size, 0)

    def test_series_string(self):
        """
        Test that compute_change_points parameters are validated.
        """
        e_divisive = EDivisive()
        with self.assertRaises(ValueError):
            e_divisive.compute_change_points("string")

    def test_series_empty(self):
        """
        Test that compute_change_points parameters are validated.
        """
        e_divisive = EDivisive()
        e_divisive._compute_change_points = MagicMock()

        e_divisive.compute_change_points([])

        series_arg = e_divisive._compute_change_points.call_args[0][0]
        self.assertIsInstance(series_arg, np.ndarray)
        self.assertEqual(series_arg.size, 0)

    def test_qhat_values_empty(self):
        """
        Test that qhat_values can accept an empty series.
        """
        self.assertEqual(EDivisive().qhat_values(EMPTY_NP_ARRAY).size, 0)
