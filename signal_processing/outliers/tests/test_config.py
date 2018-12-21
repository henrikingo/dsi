"""
Unit tests for signal_processing/change_points.py.
"""
# pylint: disable=missing-docstring
from __future__ import print_function
import unittest

from mock import MagicMock, patch, mock_open

from signal_processing.outliers.config import normalize_series, \
    standardize_series, mask_outliers, plot_confirmed_outliers, plot_without_confirmed_outliers, \
    plot_without_any_outliers, plot_test_scores, plot_probability, \
    plot_histogram, plot_gesd, TestGesd, config_gesd
import numpy as np


class TestNormalizeSeries(unittest.TestCase):
    """ Test normalize. """

    def test(self):
        series = [1] * 10 + [2] * 10
        expected = [0] * 10 + [1] * 10
        actual = normalize_series(series)
        self.assertTrue(np.array_equal(expected, actual))


class TestStandardizeSeries(unittest.TestCase):
    """ Test normalize. """

    def test(self):
        np.random.seed(seed=31415)
        series = np.random.normal(loc=0, scale=1, size=10)
        actual = standardize_series(series)
        expected = [
            0.76040552, 0.54432202, 1.70745568, -0.77469731, -1.63594058, 1.06540538, -0.26754535,
            0.37437235, -0.80422348, -0.96955423
        ]
        close = np.isclose(actual, expected)
        self.assertTrue(all(close))


class TestMaskOutliers(unittest.TestCase):
    """ Test normalize. """

    def test(self):
        outliers = range(5, 10, 1)
        series = range(10)
        mask = mask_outliers(series, outliers)
        self.assertTrue(np.array_equal(mask.compressed(), range(5)))


class TestPlotConfirmedOutliers(unittest.TestCase):
    """ Test normalize. """

    def _test(self, new_ax=False):
        x_values = np.arange(10)
        series = np.zeros(10, dtype=float)
        outliers = np.array([1], dtype=int)
        suspicious = np.array([2], dtype=int)
        mock_ax = MagicMock(name='ax')
        mock_plt = MagicMock(name='matplotlib')
        mock_plt.subplot.return_value = mock_ax
        pos = plot_confirmed_outliers(
            mock_plt,
            1,
            1,
            1,
            x_values,
            series,
            outliers,
            suspicious,
            axis=None if new_ax else mock_ax)
        if new_ax:
            mock_plt.subplot.assert_called_once_with(1, 1, 2)
            self.assertEquals(2, pos)
        else:
            mock_plt.subplot.assert_not_called()
            self.assertEquals(1, pos)

    def test_create_subplot(self):
        self._test()

    def test_use_subplot(self):
        self._test(True)


class TestPlotWithoutConfirmedOutliers(unittest.TestCase):
    """ Test normalize. """

    def _test(self, new_ax=False):
        x_values = np.arange(10)
        series = np.zeros(10, dtype=float)
        outliers = np.array([1], dtype=int)
        suspicious = np.array([2], dtype=int)
        mock_ax = MagicMock(name='ax')
        mock_plt = MagicMock(name='matplotlib')
        mock_plt.subplot.return_value = mock_ax
        pos = plot_without_confirmed_outliers(
            mock_plt,
            1,
            1,
            1,
            x_values,
            series,
            outliers,
            suspicious,
            axis=None if new_ax else mock_ax)
        if new_ax:
            mock_plt.subplot.assert_called_once_with(1, 1, 2)
            self.assertEquals(2, pos)
        else:
            mock_plt.subplot.assert_not_called()
            self.assertEquals(1, pos)

    def test_create_subplot(self):
        self._test()

    def test_use_subplot(self):
        self._test(True)


class TestPlotWithoutAnyOutliers(unittest.TestCase):
    """ Test normalize. """

    def _test(self, new_ax=False):
        x_values = np.arange(10)
        series = np.zeros(10, dtype=float)
        outliers = np.array([1], dtype=int)
        suspicious = np.array([2], dtype=int)
        mock_ax = MagicMock(name='ax')
        mock_plt = MagicMock(name='matplotlib')
        mock_plt.subplot.return_value = mock_ax
        pos = plot_without_any_outliers(
            mock_plt,
            1,
            1,
            1,
            x_values,
            series,
            outliers,
            suspicious,
            axis=None if new_ax else mock_ax)
        if new_ax:
            mock_plt.subplot.assert_called_once_with(1, 1, 2)
            self.assertEquals(2, pos)
        else:
            mock_plt.subplot.assert_not_called()
            self.assertEquals(1, pos)

    def test_create_subplot(self):
        self._test()

    def test_use_subplot(self):
        self._test(True)


class TestPlotTestScores(unittest.TestCase):
    """ Test plot_test_scores_v_critical_values. """

    def _test(self, new_ax=False):
        x_values = np.arange(10)
        series = np.zeros(10, dtype=float)
        outliers = np.array([1], dtype=int)
        suspicious = np.array([2], dtype=int)
        mock_ax = MagicMock(name='ax')
        mock_plt = MagicMock(name='matplotlib')
        mock_plt.subplot.return_value = mock_ax
        pos = plot_test_scores(
            mock_plt,
            1,
            1,
            1,
            x_values,
            series,
            outliers,
            suspicious,
            axis=None if new_ax else mock_ax)
        if new_ax:
            mock_plt.subplot.assert_called_once_with(1, 1, 2)
            self.assertEquals(2, pos)
        else:
            mock_plt.subplot.assert_not_called()
            self.assertEquals(1, pos)

    def test_create_subplot(self):
        self._test()

    def test_use_subplot(self):
        self._test(True)


class TestPlotProbability(unittest.TestCase):
    """ Test plot_probability. """

    def _test(self, new_ax=False):
        series = np.zeros(10, dtype=float)
        mock_ax = MagicMock(name='ax')
        mock_plt = MagicMock(name='matplotlib')
        with patch('signal_processing.outliers.config.probplot')\
                        as mock_probplt:
            mock_plt.subplot.return_value = mock_ax
            pos = plot_probability(
                mock_plt, 1, 1, 1, series, title='title', axis=None if new_ax else mock_ax)
        mock_probplt.assert_called_once_with(series, plot=mock_ax, rvalue=True)
        if new_ax:
            mock_plt.subplot.assert_called_once_with(1, 1, 2)
            self.assertEquals(2, pos)
        else:
            mock_plt.subplot.assert_not_called()
            self.assertEquals(1, pos)

    def test_create_subplot(self):
        self._test()

    def test_use_subplot(self):
        self._test(True)


class TestPlotHistogram(unittest.TestCase):
    """ Test plot_histogram. """

    def _test(self, new_ax=False):
        series = np.zeros(10, dtype=float)
        mock_ax = MagicMock(name='ax')
        mock_plt = MagicMock(name='matplotlib')
        mock_plt.subplot.return_value = mock_ax
        pos = plot_histogram(
            mock_plt, 1, 1, 1, series, title='title', axis=None if new_ax else mock_ax)
        mock_ax.hist.assert_called_once_with(series)
        if new_ax:
            mock_plt.subplot.assert_called_once_with(1, 1, 2)
            self.assertEquals(2, pos)
        else:
            mock_plt.subplot.assert_not_called()
            self.assertEquals(1, pos)

    def test_create_subplot(self):
        self._test()

    def test_use_subplot(self):
        self._test(True)


class TestPlotGesd(unittest.TestCase):
    """ Test plot_gesd. """

    def test_mad(self):
        # pylint: disable=no-self-use
        mad = True
        size = 10
        series = np.zeros(size, dtype=float)
        outliers = np.array([1], dtype=int)
        suspicious = np.array([2], dtype=int)

        test_identifier = {}
        test_statistics = np.zeros(size, dtype=float)
        critical_values = np.ones(size, dtype=float)
        all_z_scores = np.ones(size, dtype=float)
        significance = True

        start = 0
        end = 1
        full_series = {'create_times': [str(i) + "" * 4 for i in range(end + 1)]}

        # pylint: disable=line-too-long
        with patch('signal_processing.outliers.config.get_matplotlib'),\
             patch('signal_processing.outliers.config.plot_confirmed_outliers'),\
            patch('signal_processing.outliers.config.plot_without_confirmed_outliers'),\
            patch('signal_processing.outliers.config.plot_probability'),\
            patch('signal_processing.outliers.config.plot_histogram'):

            plot_gesd(
                test_identifier,
                series,
                outliers,
                suspicious,
                test_statistics,
                critical_values,
                all_z_scores,
                mad,
                full_series,
                start,
                end,
                significance,
                standardize=True)


class TestConfigGesd(unittest.TestCase):
    """ Test config_gesd. """

    def _test_helper(self, visualize=False, save=False):
        # pylint: disable=no-self-use
        mock_command_config = MagicMock(name='change_point')
        mock_change_point = MagicMock(name='change_point')
        parameters = TestGesd(
            test_identifier={
                'project': 'PROJECT',
                'variant': 'variant',
                'task': 'task',
                'test': 'test',
                'thread_level': 'thread_level'
            },
            max_outliers=10,
            significance_level=.05,
            mad=True,
            standardize=True,
            use_subseries=True,
            visualize=visualize,
            save=save,
            change_point=mock_change_point,
            plot_critical=False)

        with patch('signal_processing.outliers.config.get_change_point_range')\
                as mock_get_change_point_range,\
             patch('signal_processing.outliers.config.gesd') as mock_gesd,\
             patch('signal_processing.outliers.config.plot_gesd')\
                     as mock_plot_gesd,\
             patch('signal_processing.outliers.config.PointsModel'),\
             patch('signal_processing.outliers.config.helpers.save_plot')\
                     as mock_save_plot,\
             patch('signal_processing.outliers.config.mkdir_p'),\
            patch('signal_processing.outliers.config.open', mock_open()):
            mock_get_change_point_range.return_value = [0, 1, [1, 2]]
            mock_gesd.return_value = [1, range(10), range(10), range(10), range(10)]

            config_gesd(parameters, mock_command_config)

        if not visualize and not save:
            mock_plot_gesd.assert_not_called()
        else:
            mock_plot_gesd.assert_called_once()

        if not save:
            mock_save_plot.assert_not_called()
        else:
            mock_save_plot.assert_called_once()

    def test_no_visualize(self):
        self._test_helper()

    def test_visualize(self):
        self._test_helper(visualize=True)

    def test_save(self):
        self._test_helper(save=True)
