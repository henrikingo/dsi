"""
Unit tests for signal_processing/outliers/replay.py.
"""
# pylint: disable=missing-docstring, protected-access, too-many-instance-attributes, no-self-use
# pylint: disable=too-many-arguments, too-many-public-methods
# pylint: disable=too-many-lines
from __future__ import print_function

import functools
import os
import unittest
from collections import deque, OrderedDict

import numpy as np
from mock import MagicMock, patch, PropertyMock, ANY

from signal_processing.outliers.detection import STANDARD_Z_SCORE
from signal_processing.outliers.gesd import GesdResult
from signal_processing.outliers.replay import GesdReplayModel, \
    ReplayGesdParams, GesdReplayView, ReplayGesdResult, GesdReplayController, BACKWARD_DIRECTION, \
    FORWARD_DIRECTION, animate, replay_gesd, MAD_SCALE

NS = 'signal_processing.outliers.replay'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestGesdReplayModelConstructor(unittest.TestCase):
    """ Test GesdReplayModel Constrictor. """

    def _test_constructor(self, standardize=False, flat=False):
        """ test helper."""
        command_params = ReplayGesdParams(
            test_identifier=dict(project='project'),
            outliers=0,
            significance=0.05,
            z_score=STANDARD_Z_SCORE,
            start_order=2,
            end_order=20)

        if flat:
            series = [3.1415] * 12
        else:
            series = range(12)

        full_series = dict(orders=range(0, 24, 2), series=series)
        mock_command_config = MagicMock(name='command_config')

        expected_series = np.array(range(1, 10), dtype=float)
        if standardize:
            if flat:
                expected_series = np.zeros(9, dtype=float)
            else:
                subseries = series[1:10]
                expected_series = (subseries - np.mean(subseries)) / np.std(subseries)

        model = GesdReplayModel(command_params, full_series, standardize, mock_command_config)
        self.assertEquals(1, model.start)
        self.assertEquals(10, model.end)
        self.assertTrue(np.allclose(expected_series, model.series))
        self.assertTrue(np.array_equal(range(2, 20, 2), model.orders))
        self.assertEquals(9, len(model.gesd_results))

    def test_constructor(self):
        """ test GesdReplayModel constructor."""
        self._test_constructor()

    def test_standardize(self):
        """ test GesdReplayModel constructor with standardize."""
        self._test_constructor(standardize=True)

    def test_standardize_flat(self):
        """ test GesdReplayModel constructor with standardize and 0 standard deviation."""
        self._test_constructor(standardize=True, flat=True)


def create_model(outliers=0, length=12):
    standardize = False
    command_params = ReplayGesdParams(
        test_identifier=dict(project='project'),
        outliers=outliers,
        significance=0.05,
        z_score=STANDARD_Z_SCORE,
        start_order=2,
        end_order=20)

    series = range(length)
    full_series = dict(orders=range(0, 2 * length, 2), series=series)
    mock_command_config = MagicMock(name='command_config')
    return GesdReplayModel(command_params, full_series, standardize, mock_command_config)


class TestGesdReplayModelGetItem(unittest.TestCase):
    """ Test GesdReplayModel array access. """

    def _test_array_access(self, outliers=True, length=12):
        """ test array access."""
        model = create_model(outliers=0 if outliers else 20, length=length)
        for i in range(len(model.series)):
            with patch(ns('gesd')) as mock_gesd, \
                    patch(ns('ReplayGesdResult')) as mock_clazz, \
                    patch(ns('check_max_outliers')) as mock_check_max_outliers:
                result = model[i]
                result1 = model[i]
                self.assertEquals(result, result1)
                mock_clazz.assert_called_once()
                if i <= 5 or not outliers:
                    mock_check_max_outliers.assert_not_called()
                else:
                    mock_check_max_outliers.assert_called_once()

                if i <= 5:
                    mock_gesd.assert_not_called()
                else:
                    if outliers == 0:
                        mock_gesd.assert_called_once()
                    else:
                        if outliers:
                            mock_gesd.assert_called_once()
                        else:
                            num_outliers = i / 5
                            mock_gesd.assert_called_once_with(
                                ANY, num_outliers, significance_level=ANY, mad=ANY)

    def test_array_access(self):
        """ test array access."""
        self._test_array_access()

    def test_array_access_20(self):
        """ test array access."""
        self._test_array_access(outliers=False)

    def test_array_99(self):
        """ test array access."""
        outliers = False
        length = 12
        model = create_model(outliers=99, length=length)
        for i in range(len(model.series)):
            with patch(ns('gesd')) as mock_gesd, \
                    patch(ns('ReplayGesdResult')) as mock_clazz, \
                    patch(ns('check_max_outliers')) as mock_check_max_outliers:
                result = model[i]
                result1 = model[i]
                self.assertEquals(result, result1)
                mock_clazz.assert_called_once()
                if i <= 5 or not outliers:
                    mock_check_max_outliers.assert_not_called()
                else:
                    mock_check_max_outliers.assert_called_once()

                if i <= 5:
                    mock_gesd.assert_not_called()
                else:
                    num_outliers = i
                    mock_gesd.assert_called_once_with(
                        ANY, num_outliers, significance_level=ANY, mad=ANY)


class TestGesdReplayModelArray(unittest.TestCase):
    """ Test GesdReplayModel array access. """

    def setUp(self):
        self.model = create_model()

    def test_array_len(self):
        """ test array len."""
        self.assertEquals(len(self.model.series), len(self.model))

        # len doesn't populate the array
        self.assertListEqual([None] * len(self.model.series), self.model.gesd_results)

    def test_array_iterator(self):
        """ test array iterator."""
        expected = list(range(len(self.model.series)))
        with patch(ns('gesd')), \
                patch(ns('ReplayGesdResult')) as mock_clazz, \
                patch(ns('check_max_outliers')):
            mock_clazz.side_effect = expected
            for _ in range(len(self.model.series)):
                results = list(iter(self.model))
        self.assertListEqual(expected, results)


class TestGesdReplayViewConstructor(unittest.TestCase):
    """ Test GesdReplayView. """

    def test_constructor(self):
        """ test constructor."""
        mock_fig = MagicMock(name='figure')
        mock_axis = MagicMock(name='axis')
        with patch(ns('Rectangle')) as mock_clazz:
            mock_axis.plot.side_effect = [(i, ) for i in range(6)]
            mock_axis.text.side_effect = list(range(6, 9))
            mock_clazz.return_value = 9
            view = GesdReplayView(mock_fig, mock_axis)
            self.assertIsNone(view.controller)
            self.assertListEqual(list(range(10)), view.artists)


class TestGesdReplayViewArray(unittest.TestCase):
    """ Test GesdReplayView Array. """

    def setUp(self):
        mock_fig = MagicMock(name='figure')
        mock_axis = MagicMock(name='axis')
        mock_axis.plot.return_value = (1, )
        self.controller = MagicMock(name='controller')
        self.model = list(range(10))

        self.view = GesdReplayView(mock_fig, mock_axis)
        self.view.controller = self.controller
        self.view.model = self.model

    def test_array(self):
        """ test array access."""
        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.return_value = 1
            results = [self.view[i] for i in range(10)]
            self.assertListEqual([1] * 10, results)

    def test_len(self):
        """ test array len."""
        self.view.model = list(range(10))
        self.assertEquals(10, len(self.view))


class TestGesdReplayViewIter(unittest.TestCase):
    """ Test GesdReplayView Iterator. """

    def setUp(self):
        mock_fig = MagicMock(name='figure')
        mock_axis = MagicMock(name='axis')
        mock_axis.plot.return_value = (1, )
        self.controller = MagicMock(name='controller')
        self.model = list(range(10))

        self.view = GesdReplayView(mock_fig, mock_axis)
        self.view.controller = self.controller
        self.view.model = self.model

    def test_forwards(self):
        """ test iterate forwards. """
        self.view.model = list(range(10))
        self.controller.pause = False
        iterator = iter(self.view)
        expected = list(range(10))
        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.side_effect = lambda index: index
            results = [next(iterator) for _ in range(10)]
            self.assertEquals(expected, results)

    def test_forwards_wrap(self):
        """ test iterate forwards wrap around. """
        self.view.model = list(range(10))
        self.controller.pause = False
        iterator = iter(self.view)
        expected = list(range(10)) + [0]
        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.side_effect = lambda index: index
            results = [next(iterator) for _ in range(11)]
            self.assertEquals(expected, results)

    def test_backwards(self):
        """ test iterate backwards. """
        self.view.model = list(range(10))
        self.view.direction = -1
        self.controller.pause = False
        iterator = iter(self.view)
        expected = deque(list(reversed(range(10))))
        expected.rotate(1)
        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.side_effect = lambda index: index
            results = [next(iterator) for _ in range(10)]
            self.assertEquals(list(expected), results)

    def test_backwards_wrap(self):
        """ test iterate backwards wrap around. """
        self.view.model = list(range(10))
        self.view.direction = -1
        self.controller.pause = False
        iterator = iter(self.view)
        expected = deque(list(reversed(range(10))))
        expected.rotate(1)
        expected += [0]
        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.side_effect = lambda index: index
            results = [next(iterator) for _ in range(11)]
            self.assertEquals(list(expected), results)

    def test_paused_forwards(self):
        """ test iterate paused forwards. """
        length = 10
        self.view.model = list(range(length))
        self.controller.pause = True
        iterator = iter(self.view)
        expected = [0] * length
        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.side_effect = lambda index: index
            results = [next(iterator) for _ in range(length)]
            self.assertListEqual(expected, results)

    def test_paused_backwards(self):
        """ test iterate paused backwards. """
        length = 10
        self.view.model = list(range(length))
        self.view.direction = -1
        self.controller.pause = True
        iterator = iter(self.view)
        expected = [0] * length
        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.side_effect = lambda index: index
            results = [next(iterator) for _ in range(length)]
            self.assertListEqual(expected, results)

    def test_paused_step_forwards(self):
        """ test iterate paused step forwards. """
        length = 10
        steps = 3
        self.view.model = list(range(length))
        self.view.step = steps

        self.controller.pause = True
        iterator = iter(self.view)
        expected = range(steps) + [steps] * (length - steps)
        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.side_effect = lambda index: index
            results = [next(iterator) for _ in range(length)]
            self.assertListEqual(expected, results)

    def test_paused_step_backwards(self):
        """ test iterate paused step backwards. """
        length = 10
        steps = 3
        self.view.model = list(range(length))
        self.view.step = -steps
        self.view.direction = -1

        self.controller.pause = True
        iterator = iter(self.view)
        expected = deque(list(reversed(range(10))))
        expected.rotate(1)
        expected = list(expected)

        expected = expected[:steps] + [length - steps] * (length - steps)
        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.side_effect = lambda index: index
            results = [next(iterator) for _ in range(length)]
            self.assertListEqual(expected, results)

    def test_walk(self):
        """ test iterate a walk about. """
        length = 10
        self.view.model = list(range(length))
        self.controller.pause = False

        iterator = iter(self.view)
        expected = [
            0, 1, 2, 3, 4, 3, 2, 1, 0, 1, 2, 2, 2, 2, 1, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0,
            1, 2, 3, 4, 5, 6, 7, 8, 9, 0
        ]

        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.side_effect = lambda index: index
            # forwards 5
            results = [next(iterator) for _ in range(5)]

            # backwards 4
            self.view.direction = -1
            results += [next(iterator) for _ in range(4)]

            steps = 2
            # pause / step 2, 5 iterations
            self.controller.pause = True
            self.view.step = steps
            results += [next(iterator) for _ in range(5)]

            steps = -2
            # pause / step 2, 5 iterations
            self.controller.pause = True
            self.view.step = steps
            results += [next(iterator) for _ in range(5)]

            # forward 20
            self.controller.pause = False
            self.view.direction = 1
            results += [next(iterator) for _ in range(20)]

            self.assertListEqual(expected, results)


def get_item(item,
             start=0,
             end=10,
             series=None,
             orders=None,
             mad=True,
             significance_level=0.5,
             num_outliers=2,
             gesd_result=None):
    if series is None:
        series = range(start, end)
    if orders is None:
        orders = range(start, end)

    return ReplayGesdResult(
        item=item,
        test_identifier=dict(project='project'),
        full_series=dict(project='project'),
        start=start,
        end=end,
        series=series,
        orders=orders,
        mad=mad,
        significance_level=significance_level,
        num_outliers=num_outliers,
        gesd_result=gesd_result)


def create_gesd_result(count=1,
                       suspicious_indexes=None,
                       test_statistics='test_statistics',
                       critical_values='critical_values',
                       all_z_scores='all_z_scores'):
    if suspicious_indexes is None:
        suspicious_indexes = [5, 0]
    return GesdResult(count, suspicious_indexes, test_statistics, critical_values, all_z_scores)


class TestGesdReplayView(unittest.TestCase):
    """ Test GesdReplayView. """

    def setUp(self):
        mock_fig = MagicMock(name='figure')
        mock_axis = MagicMock(name='axis')
        mock_axis.plot.return_value = (1, )
        self.controller = MagicMock(name='controller')
        self.model = list(range(10))

        self.view = GesdReplayView(mock_fig, mock_axis)
        self.view.controller = self.controller
        self.view.model = self.model

    def test_init_view(self):
        """ test init_view. """
        self.view.mean = MagicMock(name='mean')
        self.view.median = MagicMock(name='median')

        with patch.object(self.view, 'get_frame') as mock_get_frame:
            mock_get_frame.side_effect = lambda index: index
            self.controller.command_params.z_score.return_value = STANDARD_Z_SCORE
            self.assertEquals(0, self.view.init_view())

            self.view.mean.set_visible.assert_called_once_with(False)
            self.view.median.set_visible.assert_called_once_with(True)


class TestGesdReplayViewGetFrame(unittest.TestCase):
    """ Test GesdReplayView. """

    def setUp(self):
        mock_fig = MagicMock(name='figure')
        mock_axis = MagicMock(name='axis')
        mock_axis.plot.return_value = (1, )
        self.controller = MagicMock(name='controller')
        self.model = list(range(10))

        self.view = GesdReplayView(mock_fig, mock_axis)
        self.view.controller = self.controller
        self.view.model = self.model

    def _test_get_frame(self, frame=6, ticker=True, length=10, frames=10, gesd_result=None):
        """ test get frame helper. """
        self.view.ticker = ticker
        self.view.model = MagicMock(name='model')
        self.view.model.series.return_value = [1] * frames

        self.view.model.__getitem__.side_effect = functools.partial(
            get_item, end=length, gesd_result=gesd_result)
        self.view.get_frame(frame)

    def test_get_frame(self):
        """ test get frame. """
        self._test_get_frame(ticker=False)

    def test_get_frame_ticker(self):
        """ test get frame ticker mode. """
        self._test_get_frame(frame=0, frames=1)

    def test_get_frame_6(self):
        """ test get 6th frame. """
        self._test_get_frame(gesd_result=create_gesd_result())


class TestGesdReplayViewRenderTrend(unittest.TestCase):
    """ Test GesdReplayView. """

    def setUp(self):
        mock_fig = MagicMock(name='figure')
        mock_axis = MagicMock(name='axis')
        mock_axis.plot.return_value = (1, )
        self.controller = MagicMock(name='controller')
        self.model = list(range(10))

        self.view = GesdReplayView(mock_fig, mock_axis)
        self.view.controller = self.controller
        self.view.model = self.model

    def _test_render_trend(self, full=False, ticker=True):
        """ test get frame helper. """
        frame = 6
        length = 10
        frames = 10
        gesd_result = create_gesd_result()

        self.view.performance = MagicMock(name='performance')
        self.view.mean = MagicMock(name='mean')
        self.view.median = MagicMock(name='median')

        self.view.ticker = ticker
        self.view.model = MagicMock(name='model')
        self.view.model.series.return_value = [1] * frames

        self.view.axis = MagicMock(name='axis')
        if full:
            self.view.full = MagicMock(name='full')

        series = np.array(range(length - 1) + [1000], dtype=float)
        orders = np.array(range(length), dtype=int)
        average = np.mean(series)
        median = np.median(series)

        self.view.model.__getitem__.side_effect = functools.partial(
            get_item, end=length, series=series, orders=orders, gesd_result=gesd_result)
        self.view.axis.plot.return_value = ['plot']

        self.view._render_trend(frame)

        if not ticker and not full:
            self.view.axis.plot.assert_called_once_with(
                self.view.model.orders, self.view.model.series, visible=False)
        else:
            self.view.axis.plot.assert_not_called()

        self.view.mean.set_data.assert_called_once_with(orders, [average] * length)
        self.view.median.set_data.assert_called_once_with(orders, [median] * length)
        self.view.performance.set_data.assert_called_once_with(orders, series)

    def test_render_trend(self):
        """ test _render_trend. """
        self._test_render_trend(ticker=False)

    def test_render_trend_ticker(self):
        """ test _render_trend. """
        self._test_render_trend()

    def test_render_trend_ticker_full(self):
        """ test _render_trend where full line was already plotted. """
        self._test_render_trend(full=True)


class TestGesdReplayViewRenderSigma(unittest.TestCase):
    """ Test GesdReplayView. """

    def setUp(self):
        mock_fig = MagicMock(name='figure')
        mock_axis = MagicMock(name='axis')
        mock_axis.plot.return_value = (1, )
        self.controller = MagicMock(name='controller')
        self.model = list(range(10))

        self.view = GesdReplayView(mock_fig, mock_axis)
        self.view.controller = self.controller
        self.view.model = self.model

    # pylint: disable=too-many-locals
    def _test_render_sigma(self, mad=False):
        """ test get frame helper. """
        frame = 6
        ticker = True
        length = 10
        frames = 10
        gesd_result = create_gesd_result()

        self.view.sigma_bounding_box = MagicMock(name='sigma_bounding_box')

        self.view.ticker = ticker
        self.view.model = MagicMock(name='model')
        self.view.model.series.return_value = [1] * frames

        self.view.axis = MagicMock(name='axis')

        series = np.array(range(length - 1) + [1000], dtype=float)
        orders = np.array(range(length), dtype=int)
        average = np.mean(series)
        median = np.median(series)
        sigma = np.std(series)

        self.view.model.__getitem__.side_effect = functools.partial(
            get_item, end=length, series=series, orders=orders, gesd_result=gesd_result, mad=mad)
        self.view.axis.plot.return_value = ['plot']

        self.view._render_sigma(frame)

        sigma_range = 3.0
        if mad:
            sigma_range /= MAD_SCALE
            center = median
        else:
            center = average

        width = frame
        height = sigma_range * sigma * 2
        x_position = 0
        y_position = center - sigma * sigma_range

        self.view.sigma_bounding_box.set_width.assert_called_once_with(width)
        self.view.sigma_bounding_box.set_height.assert_called_once_with(height)
        self.view.sigma_bounding_box.set_xy.assert_called_once_with([x_position, y_position])

    def test_render_sigma(self):
        """ test _render_trend. """
        self._test_render_sigma()

    def test_render_sigma_mad(self):
        """ test _render_trend. """
        self._test_render_sigma(mad=True)


class TestGesdReplayViewRenderOutliers(unittest.TestCase):
    """ Test GesdReplayView. """

    def setUp(self):
        mock_fig = MagicMock(name='figure')
        mock_axis = MagicMock(name='axis')
        mock_axis.plot.return_value = (1, )
        self.controller = MagicMock(name='controller')
        self.model = list(range(10))

        self.view = GesdReplayView(mock_fig, mock_axis)
        self.view.controller = self.controller
        self.view.model = self.model

    def _test_render_outliers(self, frame=0, ticker=True, length=10, frames=1, gesd_result=None):
        """ test get frame helper. """
        self.view.outliers = MagicMock(name='outliers')
        self.view.suspicious = MagicMock(name='suspicious')
        self.view.automatic = MagicMock(name='automatic')

        self.view.ticker = ticker
        self.view.model = MagicMock(name='model')
        self.view.model.series.return_value = [1] * frames

        self.view.axis = MagicMock(name='axis')

        series = np.array(range(length - 1) + [1000], dtype=float)
        orders = np.array(range(length), dtype=int)

        self.view.model.__getitem__.side_effect = functools.partial(
            get_item, end=length, series=series, orders=orders, gesd_result=gesd_result)
        self.view.axis.plot.return_value = ['plot']

        if gesd_result is not None:
            suspicious_indexes = gesd_result.suspicious_indexes
            count = gesd_result.count
            outliers = suspicious_indexes[:count]
            suspicious = suspicious_indexes[count:]
        else:
            outliers = []
            suspicious = []

        self.view._render_outliers(frame)

        expected_orders = outliers
        expected_series = outliers
        self.view.outliers.set_data.assert_called_once_with(expected_orders, expected_series)

        expected_orders = suspicious
        expected_series = suspicious
        self.view.suspicious.set_data.assert_called_once_with(expected_orders, expected_series)

        if frame in outliers:
            expected_orders = [frame]
            expected_series = [frame]
        else:
            expected_orders = []
            expected_series = []
        self.view.automatic.set_data.assert_called_once_with(expected_orders, expected_series)

    def test_render_outliers(self):
        """ test _render_trend. """
        self._test_render_outliers(frame=6, frames=10, gesd_result=create_gesd_result())

    def test_render_outliers_automatic(self):
        """ test _render_trend. """
        self._test_render_outliers(
            frame=6, frames=10, gesd_result=create_gesd_result(suspicious_indexes=[6, 0]))


class TestGesdReplayViewRenderText(unittest.TestCase):
    """ Test GesdReplayView. """

    def setUp(self):
        mock_fig = MagicMock(name='figure')
        mock_axis = MagicMock(name='axis')
        mock_axis.plot.return_value = (1, )
        self.controller = MagicMock(name='controller')
        self.model = list(range(10))

        self.view = GesdReplayView(mock_fig, mock_axis)
        self.view.controller = self.controller
        self.view.model = self.model

    def _test_render_text(self, flat=False):
        """ test get frame helper. """
        frame = 6
        ticker = True
        length = 10
        frames = 10

        self.view.time_text = MagicMock(name='time_text')
        self.view.percent_text = MagicMock(name='percent_text')
        self.view.z_score_text = MagicMock(name='z_score_text')

        self.view.ticker = ticker
        self.view.model = MagicMock(name='model')
        self.view.model.series.return_value = [1] * frames

        self.view.axis = MagicMock(name='axis')

        if not flat:
            series = np.array(range(length - 1) + [1000], dtype=float)
        else:
            series = np.ones(length, dtype=float)

        orders = np.array(range(length), dtype=int)

        self.view.model.__getitem__.side_effect = functools.partial(
            get_item, end=length, series=series, orders=orders)
        self.view.axis.plot.return_value = ['plot']

        self.view._render_text(frame)

        self.view.time_text.set_text.assert_called_once_with('  6 / 0')
        if flat:
            self.view.z_score_text.set_text.assert_not_called()
            expected_percent = '+0.000'
        else:
            self.view.z_score_text.set_text.assert_called_once_with('+3.000')
            expected_percent = '+865.251'
        self.view.percent_text.set_text.assert_called_once_with(expected_percent)

    def test_render_text(self):
        """ test _render_trend. """
        self._test_render_text()

    def test_render_text_flat(self):
        """ test _render_trend. """
        self._test_render_text(flat=True)


class TestGesdReplayViewUpdateLimits(unittest.TestCase):
    """ Test GesdReplayView. """

    def setUp(self):
        mock_fig = MagicMock(name='figure')
        mock_axis = MagicMock(name='axis')
        mock_axis.plot.return_value = (1, )
        self.controller = MagicMock(name='controller')
        self.model = list(range(10))

        self.view = GesdReplayView(mock_fig, mock_axis)
        self.view.controller = self.controller
        self.view.model = self.model

    # def _test_update_limits(self, frame=6, ticker=True, length=10, flat=False, mad=True):
    def _test_update_limits(self, frame=6, ticker=True, length=10, flat=False):
        """ test get frame helper. """
        self.view.ticker = ticker
        self.view.model = MagicMock(name='model')

        self.view.axis = MagicMock(name='axis')

        if not flat:
            series = np.array(range(length - 1) + [1000], dtype=float)
        else:
            series = np.ones(length, dtype=float)

        orders = np.array(range(length), dtype=int)
        self.view.model.series = series
        self.view.model.orders = orders

        self.view.model.__getitem__.side_effect = functools.partial(
            get_item, end=length, series=series, orders=orders)
        self.view.axis.plot.return_value = ['plot']

        self.view._update_limits(frame)

        if not flat:
            self.view.axis.set_ylim.assert_called_once()
        else:
            self.view.axis.set_ylim.assert_not_called()

        if ticker:
            self.view.axis.set_xlim.assert_called_once()
        else:
            self.view.axis.set_xlim.assert_not_called()

    def test_update_limits_ticker(self):
        """ test _render_trend. """
        self._test_update_limits()

    def test_update_limits_ticker_flat(self):
        """ test _render_trend. """
        self._test_update_limits(flat=True)

    def test_update_limits_mad(self):
        """ test _render_trend. """
        self._test_update_limits(ticker=False)

    def test_update_limits(self):
        """ test _render_trend. """
        # self._test_update_limits(ticker=False, mad=False)
        self._test_update_limits(ticker=False)

    def test_update_limits_flat(self):
        """ test _render_trend. """
        # self._test_update_limits(ticker=False, mad=False, flat=True)
        self._test_update_limits(ticker=False, flat=True)


class TestGesdReplayController(unittest.TestCase):
    """ Test GesdReplayController. """

    def test_constructor(self):
        """ test constructor."""
        mock_command_params = MagicMock(name='command_params')
        mock_command_config = MagicMock(name='command_config')
        with patch(ns('get_matplotlib')):
            GesdReplayController(mock_command_params, True, mock_command_config)


class TestGesdReplayControllerProperties(unittest.TestCase):
    """ Test GesdReplayController properties. """

    def setUp(self):
        mock_command_params = MagicMock(
            name='command_params',
            test_identifier=dict(
                project='project',
                variant='variant',
                task='task',
                test='test',
                thread_level='thread_level'))
        mock_command_config = MagicMock(name='command_config')
        with patch(ns('get_matplotlib')):
            self.controller = GesdReplayController(mock_command_params, True, mock_command_config)
        self.controller.plt = MagicMock(name='plt')

    def test_time_series(self):
        """ test time_series."""
        mock_time_series = MagicMock(name='time_series')
        mock_model = MagicMock(name='model')
        mock_model.get_points.return_value = mock_time_series
        with patch(ns('PointsModel')) as mock_clazz:
            mock_clazz.return_value = mock_model
            self.assertEquals(self.controller.time_series, mock_time_series)
            self.assertEquals(self.controller.time_series, mock_time_series)
            mock_clazz.assert_called_once()
            mock_model.get_points.assert_called_once()

    def test_gesd_model(self):
        """ test gesd_model."""
        mock_model = MagicMock(name='model')
        mock_time_series = MagicMock(name='time_series')
        with patch(ns('GesdReplayModel')) as mock_clazz:
            mock_clazz.return_value = mock_model
            self.controller._time_series = mock_time_series
            self.assertEquals(self.controller.gesd_model, mock_model)
            self.assertEquals(self.controller.gesd_model, mock_model)
            mock_clazz.assert_called_once()

    def test_gesd_view(self):
        """ test gesd_view."""
        mock_view = MagicMock(name='view')
        mock_time_series = MagicMock(name='time_series')
        self.controller.plt = MagicMock(name='plt')
        with patch(ns('GesdReplayView')) as mock_clazz:
            mock_clazz.return_value = mock_view
            self.controller._time_series = mock_time_series
            self.assertEquals(self.controller.gesd_view, mock_view)
            self.assertEquals(self.controller.gesd_view, mock_view)
            mock_clazz.assert_called_once()

    def test_animator(self):
        """ test animator."""
        mock_animator = MagicMock(name='animator')
        mock_time_series = MagicMock(name='time_series')
        self.controller.plt = MagicMock(name='plt')
        self.controller._gesd_view = MagicMock(name='view')
        self.controller.model = [1]

        with patch(ns('animation.FuncAnimation')) as mock_animation:
            mock_animation.return_value = mock_animator
            self.controller._time_series = mock_time_series
            self.assertEquals(self.controller.animator, mock_animator)
            self.assertEquals(self.controller.animator, mock_animator)
            mock_animation.assert_called_once()


class TestGesdReplayControllerMethods(unittest.TestCase):
    """ Test GesdReplayController methods. """

    def setUp(self):
        mock_command_params = MagicMock(name='command_params')
        mock_command_config = MagicMock(name='command_config')
        with patch(ns('get_matplotlib')):
            self.controller = GesdReplayController(mock_command_params, True, mock_command_config)
        self.controller.plt = MagicMock(name='plt')

    def test_show(self):
        """ test show."""
        mock_animator = MagicMock(name='animator')
        mock_time_series = MagicMock(name='time_series')
        self.controller.plt = MagicMock(name='plt')
        self.controller._gesd_view = MagicMock(name='view')
        self.controller.legend = MagicMock(name='legend')
        self.controller.plt = MagicMock(name='plt')
        self.controller.model = [1]

        with patch(ns('animation.FuncAnimation')) as mock_animation:
            mock_animation.return_value = mock_animator
            self.controller._time_series = mock_time_series
            self.controller.show()

            self.assertTrue(self.controller.visible)
            self.controller.legend.set_visible.assert_called_once_with(True)
            self.controller.plt.show.assert_called_once()
            self.assertEquals(self.controller.animator, mock_animator)

    def test_show_handles_exception(self):
        """ test show exception."""
        mock_animator = MagicMock(name='animator')
        mock_time_series = MagicMock(name='time_series')
        self.controller.plt = MagicMock(name='plt')
        self.controller._gesd_view = MagicMock(name='view')
        self.controller.legend = MagicMock(name='legend')
        self.controller.plt = MagicMock(name='plt')
        self.controller.model = [1]

        with patch(ns('animation.FuncAnimation')) as mock_animation:
            mock_animation.return_value = mock_animator
            self.controller._time_series = mock_time_series
            self.controller.plt.show.side_effect = AttributeError()

            self.controller.show()

    def test_hide(self):
        """ test hide."""
        self.controller.plt = MagicMock(name='plt')

        self.controller.hide()
        self.controller.plt.close.assert_called_once()

    def _test_save(self, file_format='gif', writer='imagemagick'):
        """ save helper."""
        self.controller._animator = MagicMock(name='animator')
        self.controller.command_config = MagicMock(name='command_config', out='/out')
        self.controller.command_params = MagicMock(
            name='command_params',
            significance=1.0,
            outliers=10,
            z_score='z score',
            start_order='start order')
        self.controller.test_identifier = dict(
            project='project', variant='variant', task='task', test='test', thread_level='1000000')

        pathname = '/out/project/variant/task/test/1000000-threads/1.000000'
        filename = 'test-1000000-threads-start order-10-z score-1.0-standard.' + file_format
        full_filename = os.path.join(pathname, filename)
        with patch(ns('mkdir_p')) as mock_mkdir_p:
            self.controller.save(file_format=file_format, fps='fps', extra_args='extra_args')
            mock_mkdir_p.assert_called_once_with(pathname)
            self.controller._animator.save.assert_called_once_with(
                full_filename, fps='fps', extra_args='extra_args', writer=writer)

    def test_save(self):
        """ test save."""
        self._test_save()

    def test_save_mp4(self):
        """ test save mp4."""
        self._test_save(file_format='mp4', writer=None)


class TestGesdReplayControllerKeyEvents(unittest.TestCase):
    """ Test GesdReplayController key events. """

    def setUp(self):
        mock_command_params = MagicMock(name='command_params')
        mock_command_config = MagicMock(name='command_config')
        with patch(ns('get_matplotlib')):
            self.controller = GesdReplayController(mock_command_params, True, mock_command_config)
        self.controller.plt = MagicMock(name='plt')
        self.mock_step = MagicMock(name='step')

        self.mock_first = MagicMock(name='first')
        self.mock_second = MagicMock(name='second')
        self.mock_third = MagicMock(name='third')

        labeled_items = OrderedDict([('first', self.mock_first), ('second', self.mock_second),
                                     ('third', self.mock_third)])
        self.controller._gesd_view = MagicMock(name='direction', labeled_items=labeled_items)
        self.controller._gesd_view.step = self.mock_step

        self.mock_direction = PropertyMock(name='direction')
        type(self.controller._gesd_view).direction = self.mock_direction

    def test_space(self):
        """ test space toggles pause."""
        mock_event = MagicMock(name='event', key=' ')
        self.controller._animator = MagicMock(name='event', key=' ')

        self.controller.on_key_press(mock_event)
        self.assertTrue(self.controller.pause)
        self.controller._animator.event_source.stop.assert_called_once()
        self.controller._animator.event_source.start.assert_not_called()

        self.controller._animator = MagicMock(name='event', key=' ')
        self.controller.on_key_press(mock_event)
        self.assertFalse(self.controller.pause)
        self.controller._animator.event_source.stop.assert_not_called()
        self.controller._animator.event_source.start.assert_called_once()

    def _test_direction(self, key='left', pause=True, direction=BACKWARD_DIRECTION):
        """ test controller save mp4."""
        mock_event = MagicMock(name='event', key=key)

        self.controller.pause = pause
        self.controller.on_key_press(mock_event)

        if pause:
            self.mock_step.__iadd__.assert_called_once_with(direction)
        else:
            self.mock_direction.assert_called_once_with(direction)

    def test_left_paused(self):
        """ test left paused."""
        self._test_direction()

    def test_right_paused(self):
        """ test right paused."""
        self._test_direction(key='right', direction=FORWARD_DIRECTION)

    def test_left(self):
        """ test left not paused."""
        self._test_direction(pause=False)

    def test_right(self):
        """ test right not paused."""
        self._test_direction(key='right', pause=False, direction=FORWARD_DIRECTION)

    def test_1(self):
        """ test 1."""
        mock_event = MagicMock(name='event', key='1')
        self.mock_first.get_visible.return_value = True

        self.controller.on_key_press(mock_event)
        self.mock_first.set_visible.assert_called_once_with(False)
        self.mock_first.get_visible.assert_called_once()

    def test_3(self):
        """ test 1."""
        mock_event = MagicMock(name='event', key='3')
        self.mock_third.get_visible.return_value = False

        self.controller.on_key_press(mock_event)
        self.mock_third.set_visible.assert_called_once_with(True)
        self.mock_third.get_visible.assert_called_once()

    def test_0(self):
        """ test 0."""
        mock_event = MagicMock(name='event', key='0')
        self.mock_first.get_visible.return_value = False
        self.mock_second.get_visible.return_value = True
        self.mock_third.get_visible.return_value = False

        self.controller.on_key_press(mock_event)
        self.mock_first.set_visible.assert_called_once_with(True)
        self.mock_first.get_visible.assert_called_once()

        self.mock_second.set_visible.assert_called_once_with(False)
        self.mock_second.get_visible.assert_called_once()

        self.mock_third.set_visible.assert_called_once_with(True)
        self.mock_third.get_visible.assert_called_once()

    def test_4(self):
        """ test 4."""
        mock_event = MagicMock(name='event', key='4')

        self.controller.on_key_press(mock_event)
        self.mock_first.get_visible.assert_not_called()
        self.mock_second.get_visible.assert_not_called()
        self.mock_third.get_visible.assert_not_called()


class TestGesdReplayControllerPickEvents(unittest.TestCase):
    """ Test GesdReplayController pick events. """

    def setUp(self):
        mock_command_params = MagicMock(name='command_params')
        mock_command_config = MagicMock(name='command_config')
        with patch(ns('get_matplotlib')):
            self.controller = GesdReplayController(mock_command_params, True, mock_command_config)
        self.controller.plt = MagicMock(name='plt')

        self.mock_first = MagicMock(name='first')
        self.mock_second = MagicMock(name='second')
        self.mock_third = MagicMock(name='third')

        self.controller.fig = MagicMock(name='figure')

        labeled_items = OrderedDict([('first', self.mock_first), ('second', self.mock_second),
                                     ('third', self.mock_third)])
        self.controller._gesd_view = MagicMock(name='view', labeled_items=labeled_items)

        self.mock_first_text = MagicMock(name='first text')
        self.mock_second_text = MagicMock(name='second text')
        self.mock_third_text = MagicMock(name='third text')

        texts = [self.mock_first_text, self.mock_second_text, self.mock_third_text]

        self.mock_first_handle = MagicMock(name='first handle')
        self.mock_second_handle = MagicMock(name='second handle')
        self.mock_third_handle = MagicMock(name='third handle')

        legend_handles = [self.mock_first_handle, self.mock_second_handle, self.mock_third_handle]
        self.controller.legend = MagicMock(
            name='direction', texts=texts, legendHandles=legend_handles)

    def _test_text(self, artist=None, item=None, visible=False):
        """ test space toggles pause."""
        if artist is None:
            artist = self.mock_first_text

        if item is None:
            item = self.mock_first

        mock_event = MagicMock(name='event', artist=artist)
        item.get_visible.return_value = visible

        self.controller.on_pick(mock_event)

        item.set_visible.assert_called_once_with(not visible)
        item.get_visible.assert_called_once()

        if visible:
            artist.set_alpha.assert_called_with(1.0)
        else:
            artist.set_alpha.assert_called_with(0.2)

        self.controller.fig.canvas.draw.assert_called_once()

    def test_first_text_invisible(self):
        """ test first text not visible."""
        self._test_text()

    def test_first_handle_invisible(self):
        """ test first handle not visible."""
        self._test_text(artist=self.mock_first_handle)

    def test_second_text(self):
        """ test second text visible."""
        self._test_text(artist=self.mock_second_text, item=self.mock_second, visible=True)

    def test_second_handle(self):
        """ test second handle visible."""
        self._test_text(artist=self.mock_second_handle, item=self.mock_second, visible=True)


class TestAnimate(unittest.TestCase):
    """ Test animate. """

    def test(self):
        """ test animate."""
        expected = list(reversed(range(10)))
        iterable = iter(expected)
        results = [animate(i * 2, iterable) for i in range(10)]
        self.assertListEqual(expected, results)


class TestReplayGesd(unittest.TestCase):
    """ Test replay_gesd. """

    # pylint: disable=no-self-use, too-many-arguments
    def _test(self,
              standardize=False,
              show=True,
              save=False,
              file_format='file_format',
              error=False):
        """ test helper."""
        test_identifier = dict(
            project='project',
            variant='variant',
            task='task',
            test='test',
            thread_level='thread_level')
        mock_command_params = MagicMock(name='command_params', test_identifier=test_identifier)
        mock_command_config = MagicMock(name='command_config', file_format=file_format)
        mock_controller = MagicMock(name='controller')

        with patch(ns('get_matplotlib')), \
             patch(ns('GesdReplayController')) as mock_clazz:
            mock_clazz.return_value = mock_controller
            if error:
                mock_identifier_str = PropertyMock(name='identifier_str')
                type(mock_controller).identifier_str = mock_identifier_str
                mock_identifier_str.side_effect = KeyError()

            replay_gesd(
                mock_command_params,
                mock_command_config,
                standardize=standardize,
                show=show,
                save=save)

            mock_clazz.assert_called_once_with(mock_command_params, standardize,
                                               mock_command_config)

            if error:
                mock_controller.hide.assert_called_once()
            else:
                if show:
                    mock_controller.show.assert_called_once()
                else:
                    mock_controller.show.assert_not_called()

                if save:
                    mock_controller.save.assert_called_once_with(file_format=file_format)
                    mock_controller.hide.assert_called_once()
                else:
                    mock_controller.save.assert_not_called()
                    mock_controller.hide.assert_not_called()

    def test_show_no_save(self):
        """ test show, not save."""
        self._test()

    def test_show_save(self):
        """ test show, save."""
        self._test(save=True)

    def test_no_show_save(self):
        """ test show, save."""
        self._test(show=False, save=True)

    def test_no_show_no_save(self):
        """ test show, save."""
        self._test(show=False, save=False)

    def test_key_error(self):
        """ test show, save."""
        self._test(error=True)
