import unittest

import numpy as np

from signal_processing.change_points.weights import exponential_weights, DEFAULT_WEIGHTING


class TestExponentialWeights(unittest.TestCase):
    """
    Test exponential_weights.
    """

    def test_exponential_weights_default(self):
        """
        Test yet another start end.
        """
        expected = [
            1, 0.5506, 0.30316, 0.16692, 0.09191, 0.0506, 0.02786, 0.01534, 0.00845, 0.00465
        ]
        weights = exponential_weights(100, DEFAULT_WEIGHTING)
        self.assertTrue(np.allclose(expected, weights, rtol=1e-02))

    def test_exponential_weights_1tenth(self):
        """
        Test yet another start end.
        """
        expected = [
            1, 0.43634, 0.19039, 0.08308, 0.03625, 0.01582, 0.0069, 0.00301, 0.00131, 0.00057
        ]
        weights = exponential_weights(100, DEFAULT_WEIGHTING / 10)
        self.assertTrue(np.allclose(expected, weights, rtol=1e-02))

    def test_exponential_weights_x10(self):
        """
        Test yet another start end.
        """
        expected = [
            1, 0.69478, 0.48272, 0.33539, 0.23302, 0.1619, 0.11248, 0.07815, 0.0543, 0.03773
        ]

        weights = exponential_weights(100, DEFAULT_WEIGHTING * 10)
        self.assertTrue(np.allclose(expected, weights, rtol=1e-02))

    def test_exponential_weights_x100(self):
        """
        Test yet another start end.
        """
        expected = [1, 0.87671, 0.76863, 0.67387, 0.59079, 0.51795, 0.4541, 0.39811, 0.34903, 0.306]

        weights = exponential_weights(100, DEFAULT_WEIGHTING * 100)
        self.assertTrue(np.allclose(expected, weights, rtol=1e-02))

    def test_exponential_weights_size_200(self):
        """
        Test yet another start end.
        """
        expected = [
            1, 0.5506, 0.30316, 0.16692, 0.09191, 0.0506, 0.02786, 0.01534, 0.00845, 0.00465
        ]

        weights = exponential_weights(200, DEFAULT_WEIGHTING)
        np.set_printoptions(precision=5, suppress=True)
        print weights
        self.assertTrue(np.allclose(expected, weights, rtol=1e-02))
