"""
Render a Gesd outlier detection replay.
"""
from __future__ import print_function

import os
from collections import namedtuple, OrderedDict
from datetime import datetime

import numpy as np
import scipy
import scipy.stats
import structlog
from matplotlib import animation
from matplotlib.patches import Rectangle

from bin.common.config import is_integer
from bin.common.utils import mkdir_p
from signal_processing.commands.helpers import PORTRAIT_FIGSIZE
from signal_processing.detect_changes import PointsModel
from signal_processing.outliers.config import get_matplotlib
from signal_processing.outliers.detection import STANDARD_Z_SCORE, compute_max_outliers
from signal_processing.outliers.gesd import gesd

MAD_SCALE = 1.4826

FORWARD_DIRECTION = 1
""" Play the animation forwards. """

BACKWARD_DIRECTION = -1
""" Play the animation backwards. """

DEFAULT_INTERVAL = 200
""" The default delay between frames in milliseconds. """

LOG = structlog.getLogger(__name__)

ReplayGesdParams = namedtuple(
    'ReplayGesdParams',
    ['test_identifier', 'outliers', 'significance', 'z_score', 'start_order', 'end_order'])
"""
A named tuple for the Replay Command.

:type test_identifier: dict(str, str),
:type outliers: int
:type significance: float
:type z_score: str
:type start_order: int
:type end_order: int
"""

ReplayGesdResult = namedtuple('ReplayGesdResult', [
    'item', 'test_identifier', 'full_series', 'start', 'end', 'series', 'orders', 'mad',
    'significance_level', 'num_outliers', 'gesd_result'
])
"""
Represent the result of the outliers detection.

It contains the GESD algorithm result as well as some of the data and parameters used.
"""


# pylint: disable=too-few-public-methods, too-many-instance-attributes
class GesdReplayModel(object):
    """ Iterable class to hold the GESD data. The GESD data is lazy evaluated. """

    def __init__(self, command_params, full_series, standardize, command_config):
        """
        Create a new Replay model.

        :param ReplayGesdParams command_params: The Replay parameters for this model.
        :param dict full_series: The full time series data.
        :param CommandConfig command_config: The configuration common to all.
        """
        self.command_params = command_params
        self.full_series = full_series
        self.command_config = command_config

        self.test_identifier = command_params.test_identifier
        self.start_order = command_params.start_order
        self.end_order = command_params.end_order
        self.outliers_percentage = command_params.outliers

        self.significance_level = command_params.significance
        self.mad = command_params.z_score != STANDARD_Z_SCORE

        self.start = self.full_series['orders'].index(self.start_order)
        self.end = self.full_series['orders'].index(self.end_order)
        self.series = np.array(self.full_series['series'][self.start:self.end], dtype=float)
        if standardize:
            sigma = np.std(self.series)
            if sigma == 0.0:
                self.series = np.zeros(self.end - self.start, dtype=float)
            else:
                self.series = (self.series - np.mean(self.series)) / sigma

        self.orders = np.array(self.full_series['orders'][self.start:self.end], dtype=int)
        self.gesd_results = [None] * (self.end - self.start)

    def __getitem__(self, item):
        """
        Allow this instance to be accessed as an array. Results are lazy evaluated.

        :param int item: The index of the array element.
        :return: The replay result.
        :rtype: ReplayGesdResult.
        """
        if self.gesd_results[item] is None:
            series = self.series[:item + 1]
            orders = self.orders[:item + 1]
            if item > 5:
                num_outliers = compute_max_outliers(self.outliers_percentage, self.test_identifier,
                                                    series)

                gesd_result = gesd(
                    series, num_outliers, significance_level=self.significance_level, mad=self.mad)
            else:
                num_outliers = None
                gesd_result = None
            self.gesd_results[item] = ReplayGesdResult(
                item=item,
                test_identifier=self.test_identifier,
                full_series=self.full_series,
                start=self.start,
                end=self.end,
                series=series,
                orders=orders,
                mad=self.mad,
                significance_level=self.significance_level,
                num_outliers=num_outliers,
                gesd_result=gesd_result)
        return self.gesd_results[item]

    def __len__(self):
        """
        Get the array length.

        :return: The replay results array length.
        :rtype: int.
        """
        return len(self.gesd_results)

    def __iter__(self):
        """
        Get an iterable for the array. Results are lazy evaluated.

        :return: The replay results.
        :rtype: iterable.
        """
        return (self[x] for x in range(len(self.gesd_results)))


class GesdReplayView(object):
    """ Update the view with the model state. """

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(self, fig, axis, ticker=True, sigma_range=3.0):
        """
        Get a replay view.

        :param matplotlib.Figure fig: The matplotlib figure.
        :param matplotlib.Axes axis: The matplotlib ax.
        :param bool ticker: Interactively display the x limit (make the trend line animation scale
        on demand).
        :param float sigma_range: The number of standard deviations to render as a block range on
        the animation.
        """
        self.axis = axis
        self.fig = fig

        # line2D for the full data if we want the scaling right.
        self.full = None
        self.labeled_items = OrderedDict()

        # axis.plot returns an array of one element
        self.performance, = axis.plot([], [], 'bo-', markersize=1)
        self.labeled_items['series'] = self.performance

        self.mean, = axis.plot([], [], 'r--')
        self.labeled_items['mean'] = self.mean

        self.median, = axis.plot([], [], 'r-')
        self.labeled_items['median'] = self.median

        self.outliers, = axis.plot([], [], 'ro', markersize=10)
        self.labeled_items['outliers'] = self.outliers

        self.suspicious, = axis.plot([], [], 'k*', markersize=10)
        self.labeled_items['suspicious'] = self.suspicious

        self.automatic, = axis.plot([], [], 'r*', markersize=20)
        self.labeled_items['automatic'] = self.automatic

        self.time_text = axis.text(0.9, 0.02, '', transform=axis.transAxes)
        self.percent_text = axis.text(0.9, 0.06, '', transform=axis.transAxes)
        self.z_score_text = axis.text(0.9, 0.1, '', transform=axis.transAxes)

        # Add a rectangle for the bounding box of standard deviations.
        self.sigma_bounding_box = Rectangle((0, 0), 0, 0, fc='c', alpha=0.25)
        axis.add_patch(self.sigma_bounding_box)

        self.artists = [
            self.performance, self.mean, self.median, self.outliers, self.suspicious,
            self.automatic, self.time_text, self.percent_text, self.z_score_text,
            self.sigma_bounding_box
        ]
        self.automatic_indexes = set()
        self.ticker = ticker
        self.sigma_range = sigma_range
        self.model = None
        self.direction = 1
        self.step = 0
        self.controller = None

    def __getitem__(self, item):
        """
        Get the matplotlib artists for the frame at index *item*.

        :param int item: The index of the array element.
        :return: The matplotlib artists.
        :rtype: list(matplotlib.Artist).
        """
        return self.get_frame(item)

    def __len__(self):
        """
        Get the array length.

        :return: The number of frames.
        :rtype: int.
        """
        return len(self.model)

    def __iter__(self):
        """
        Get an iterable for the array. This iterable behaves more like itertools.cycle than a
        standard iterable.

        :return: The artists.
        :rtype: iterable.
        """
        i = 0
        while True:
            yield self[i]
            if self.controller.pause:
                if self.step > 0:
                    i += FORWARD_DIRECTION
                    self.step -= 1
                elif self.step < 0:
                    i += BACKWARD_DIRECTION
                    self.step += 1
            else:
                i += self.direction

            i = i % len(self.model)
            if i < 0:
                i = len(self.model) - 1

            self.automatic_indexes = {x for x in self.automatic_indexes if x <= i - 1}

            LOG.debug('iter', automatic_indexes=self.automatic_indexes, i=i)

    def init_view(self):
        """ Initialize the view and then set the visibility of the mean / median lines. """
        artists = self.get_frame(0)
        self.mean.set_visible(self.controller.command_params.z_score == STANDARD_Z_SCORE)
        self.median.set_visible(self.controller.command_params.z_score != STANDARD_Z_SCORE)
        return artists

    def _render_trend(self, frame):
        """
        render the trend lines for a given frame.

        :param int frame: The frame number.
        """
        replay_result = self.model[frame]
        average = np.mean(replay_result.series)
        median = np.median(replay_result.series)

        # Set the full (hidden) trend line data, this will calculate sane view bounds.
        if not self.ticker and self.full is None:
            self.full, = self.axis.plot(self.model.orders, self.model.series, visible=False)

        # Update mean and median lines.
        size = len(replay_result.orders)
        self.mean.set_data(replay_result.orders, [average] * size)
        self.median.set_data(replay_result.orders, [median] * size)

        # Update the trend line.
        self.performance.set_data(replay_result.orders, replay_result.series)

    def _render_sigma(self, frame):
        """
        render the sigma bounding box for a given frame.

        :param int frame: The frame number.
        """
        replay_result = self.model[frame]
        average = np.mean(replay_result.series)
        median = np.median(replay_result.series)
        sigma = np.std(replay_result.series)

        if replay_result.mad:
            sigma_range = self.sigma_range / MAD_SCALE
            center = median
        else:
            sigma_range = self.sigma_range
            center = average

        x = replay_result.orders[0]
        width = replay_result.orders[replay_result.item] - replay_result.orders[0]

        y = center - sigma * sigma_range
        height = sigma_range * sigma * 2

        LOG.debug('rectangle', width=width, height=height, x=x, y=y)
        self.sigma_bounding_box.set_width(width)
        self.sigma_bounding_box.set_height(height)
        self.sigma_bounding_box.set_xy([x, y])

    def _render_outliers(self, frame):
        """
        render the outlier scatters for a given frame.

        :param int frame: The frame number.
        """
        if frame <= 5:
            self.automatic_indexes = set()

        outliers = []
        low_confidence_outliers = []
        replay_result = self.model[frame]

        gesd_result = replay_result.gesd_result
        if gesd_result is not None:
            indexes = gesd_result.suspicious_indexes
            count = gesd_result.count
            outliers = indexes[:count]
            low_confidence_outliers = indexes[count:]

        if outliers:
            self.outliers.set_data(replay_result.orders[outliers], replay_result.series[outliers])
        else:
            self.outliers.set_data([], [])

        if low_confidence_outliers:
            self.suspicious.set_data(replay_result.orders[low_confidence_outliers],
                                     replay_result.series[low_confidence_outliers])
        else:
            self.suspicious.set_data([], [])

        if replay_result.item in outliers:
            self.automatic_indexes.add(replay_result.item)

        if self.automatic_indexes:
            self.automatic.set_data(replay_result.orders[list(self.automatic_indexes)],
                                    replay_result.series[list(self.automatic_indexes)])
        else:
            self.automatic.set_data([], [])

    def _render_text(self, frame):
        """
        render the text artists for a given frame.

        :param int frame: The frame number.
        """
        replay_result = self.model[frame]
        average = np.mean(replay_result.series)

        self.time_text.set_text("{:>3} / {}".format(replay_result.item, len(self.model.series)))
        current = replay_result.series[-1]
        percent = (current / average) - 1
        self.percent_text.set_text("{:+.3f}".format(percent * 100))

        sigma = np.std(replay_result.series)
        if len(replay_result.orders) >= 2 and sigma != 0:
            z_scores = scipy.stats.zscore(replay_result.series)
            self.z_score_text.set_text("{:+.3f}".format(z_scores[-1]))

    def _update_limits(self, frame):
        """
        Update the x and y limits for a given frame.

        :param int frame: The frame number.
        """
        replay_result = self.model[frame]
        sigma = np.std(replay_result.series)
        if self.ticker:
            # set limit 1 standard deviation beyond the extreme point
            if sigma != 0:
                average = np.mean(replay_result.series)
                y_min = min(np.min(replay_result.series), average - sigma * self.sigma_range)
                y_max = max(np.max(replay_result.series), average + sigma * self.sigma_range)
                self.axis.set_ylim(y_min - sigma / 2.0, y_max + sigma / 2.0)

            order_sigma = np.std(replay_result.orders)
            # no point setting limits if bottom and top are the same
            if order_sigma != 0:
                self.axis.set_xlim(
                    min(replay_result.orders) - order_sigma / 10.0,
                    max(replay_result.orders) + order_sigma / 10.0)
        else:
            model_sigma = np.std(self.model.series)
            if model_sigma != 0:
                if replay_result.mad:
                    model_center = np.median(self.model.series)
                else:
                    model_center = np.mean(self.model.series)

                y_min = np.min(self.model.series)
                y_min = min(y_min, model_center - model_sigma * self.sigma_range)

                y_max = np.max(self.model.series)
                y_max = max(y_max, model_center + model_sigma * self.sigma_range)

                self.axis.set_ylim(y_min - sigma / 2.0, y_max + sigma / 2.0)

    def get_frame(self, frame):
        """
        Get all the matplotlib artists for the GESD results for frame index in the model.

        :param frame: The current item.
        :return: The artists.
        :rtype: list(matplotlib.Artist).
        """
        try:
            self._render_trend(frame)
            self._render_sigma(frame)
            self._render_outliers(frame)
            self._render_text(frame)
            self._update_limits(frame)
        # pylint: disable=broad-except
        except Exception as e:
            print(e)
            LOG.exception('error', exc_info=1)

        return self.artists


# pylint: disable=too-many-instance-attributes
class GesdReplayController(object):
    """ Coordinate Gesd Replay. """

    def __init__(self, command_params, standardize, command_config):
        """
        Get a replay controller. This object mediates between the UI events, the View and the
        model.

        :param ReplayGesdParams command_params: The Replay parameters for this model.
        :param CommandConfig command_config: The configuration common to all.
        """
        self.command_params = command_params
        self.command_config = command_config

        self.test_identifier = command_params.test_identifier
        self.start_order = command_params.start_order
        self.end_order = command_params.end_order
        self.plt = get_matplotlib()

        self.pause = False
        self.sigma_range = 3.0
        self.identifier_str = None

        self._time_series = None
        self._gesd_model = None
        self._gesd_view = None

        self._animator = None
        self.ticker = False
        self.visible = False
        self.fig = None
        self.interval = DEFAULT_INTERVAL
        self.standardize = standardize
        self.legend = None
        self.blit = False

    @property
    def time_series(self):
        """
        Get the full time series data for this graph. Results are lazy evaluated.

        :return: The full time series data for a given test_identifier and change point.
        :rtype: dict().
        """
        if self._time_series is None:
            model = PointsModel(
                self.command_config.mongo_uri,
                0,
                mongo_repo=self.command_config.mongo_repo,
                credentials=self.command_config.credentials)
            self._time_series = model.get_points(self.test_identifier, 0)
        LOG.debug("time_series", time_series=self._time_series)
        return self._time_series

    @property
    def gesd_model(self):
        """
        Get the gesd model for this graph.

        :return: The gesd model data.
        :rtype: GesdReplayModel.
        """
        if self._gesd_model is None:
            self._gesd_model = GesdReplayModel(self.command_params, self.time_series,
                                               self.standardize, self.command_config)
        LOG.debug("gesd_model", len=len(self._gesd_model))
        return self._gesd_model

    @property
    def gesd_view(self):
        """
        Get the gesd view for this graph.

        :return: The gesd view instance.
        :rtype: GesdReplayView.
        """

        if self._gesd_view is None:
            fig_size = (PORTRAIT_FIGSIZE[0], PORTRAIT_FIGSIZE[1] / 2)

            fig = self.plt.figure(figsize=fig_size)
            self.fig = fig

            fig.canvas.mpl_connect('key_press_event', self.on_key_press)

            axis = fig.add_subplot(1, 1, 1)
            axis.grid()
            title = '{project} {variant} {task}\n{test}\n{thread_level}'.format(
                **self.test_identifier)
            axis.set_title(title, fontsize=14, fontweight='bold')

            # The number of steps in the full cycle.
            self._gesd_view = GesdReplayView(
                fig, axis, ticker=self.ticker, sigma_range=self.sigma_range)
            self._gesd_view.controller = self

            labeled_items = self._gesd_view.labeled_items
            self.legend = axis.legend(
                [
                    value if not isinstance(value, list) else value[0]
                    for value in labeled_items.values()
                ],
                labeled_items.keys(),
                loc='lower left',
                fancybox=True,
                shadow=True)
            self.legend.get_frame().set_alpha(0.4)
            self.legend.set_visible(False)
            for lines in self.legend.legendHandles:
                if lines:
                    lines.set_picker(5)  # 5 pts tolerance

            for text in self.legend.texts:
                if text:
                    text.set_picker(5)  # 5 pts tolerance

            fig.canvas.mpl_connect('pick_event', self.on_pick)

            self._gesd_view.model = self.gesd_model
        return self._gesd_view

    @property
    def animator(self):
        """
        Get the gesd animator.

        :return: The gesd animator.
        :rtype: animation.FuncAnimation.
        """
        if self._animator is None:
            steps = len(self.gesd_model)
            frames = None if self.visible else len(self.gesd_model)
            self._animator = animation.FuncAnimation(
                self.gesd_view.fig,
                animate,
                init_func=self.gesd_view.init_view,
                fargs=(
                    self,
                    iter(self.gesd_view),
                ),
                frames=frames,
                interval=self.interval,
                blit=self.blit,
                repeat=True,
                save_count=steps)

            self.plt.subplots_adjust(hspace=1.5)
            self.plt.tight_layout()

        return self._animator

    def show(self):
        """ Show the animation. """
        self.visible = True

        _ = self.animator
        self.legend.set_visible(True)
        try:
            self.plt.show()
        except AttributeError:
            pass

    def hide(self):
        """ Hide the animation. """
        self.plt.close()

    def _filename(self, file_format):
        """
        Create filename from instance variables and file_format.

        :param str file_format: The file format to save.
        :return: The full filename..
        :rtype: str.
        """
        pathname = os.path.join(self.command_config.out, self.test_identifier['project'],
                                self.test_identifier['variant'], self.test_identifier['task'],
                                self.test_identifier['test'], "{}-threads".format(
                                    self.test_identifier['thread_level']), "{:03f}".format(
                                        self.command_params.significance))

        filename_format = '{test}-{thread_level}-{start_order}-{outliers}-{mad}-' + \
            '{p}{ticker}{standard}.{file_format}'
        filename = filename_format.format(
            test=self.test_identifier['test'],
            outliers=self.command_params.outliers,
            thread_level="{}-threads".format(self.test_identifier['thread_level']),
            start_order=self.command_params.start_order,
            mad=self.command_params.z_score,
            p=self.command_params.significance,
            ticker='-ticker' if self.ticker else '',
            standard='-standard' if self.standardize else '',
            file_format=file_format)

        return os.path.join(pathname, filename)

    def save(self, file_format='gif', fps=10, extra_args=('-vcodec', 'libx264')):
        """
        Save the animation to a file.

        :param str file_format: The file format to save.
        :param int fps: The frames per second to save.
        :param list(str) extra_args: The extra args to save.
        """
        start_time = datetime.utcnow()
        LOG.debug('save starting', start_time=start_time, test_identifier=self.test_identifier)

        full_filename = self._filename(file_format)
        pathname, _ = os.path.split(full_filename)
        mkdir_p(pathname)
        LOG.info("saving", full_filename=full_filename)
        if file_format in ['gif', 'png']:
            writer = 'imagemagick'
        else:
            writer = None
        self.animator.save(full_filename, fps=fps, extra_args=extra_args, writer=writer)
        end_time = datetime.utcnow()
        LOG.debug(
            'save complete',
            dutration=str(end_time - start_time),
            start_time=start_time,
            end_time=end_time,
            full_filename=full_filename,
            test_identifier=self.test_identifier)

    # Events
    def on_key_press(self, event):
        """
        Handle a key press event.

        The following are handled:
           space: toggle animation (play / pause).
           left: play / step backwards.
           right: play / step forwards.
           0: Toggle visibility of all items.
           1-9: Toggle visibility of line in legend (1 toggles first legend item etc).
        :param matplotlib.KeyEvent event: The event.
        """
        LOG.debug("on_key_press", click=event)
        if event.key == ' ':
            self.pause ^= True
            if self.pause:
                self.animator.event_source.stop()
            else:
                self.animator.event_source.start()
            return
        if event.key in ['left', 'right']:
            if event.key == 'left':
                direction = BACKWARD_DIRECTION
            else:
                direction = FORWARD_DIRECTION

            if self.pause:
                self.animator.event_source.start()
                self.gesd_view.step += direction
            else:
                self.gesd_view.direction = direction
            return
        if is_integer(event.key):
            item_index = int(event.key) - 1
            if item_index == -1:
                for item in self.gesd_view.labeled_items.values():
                    item.set_visible(not item.get_visible())
                return
            if item_index < len(self.gesd_view.labeled_items):
                item = list(self.gesd_view.labeled_items.values())
                item[item_index].set_visible(not item[item_index].get_visible())

    def on_pick(self, event):
        """
        Handle a pick press event on a legend. Toggle visibility of the line.

        :param matplotlib.PickEvent event: The event.
        """
        LOG.debug("on_pick", pause=self.pause, click=event)
        legend_item = event.artist
        if legend_item in self.legend.texts or legend_item in self.legend.legendHandles:
            if legend_item in self.legend.texts:
                item_index = self.legend.texts.index(legend_item)
            else:
                item_index = self.legend.legendHandles.index(legend_item)
            item = list(self.gesd_view.labeled_items.values())[item_index]
            visible = item.get_visible()
            item.set_visible(not visible)
            if visible:
                legend_item.set_alpha(1.0)
            else:
                legend_item.set_alpha(0.2)
            self.fig.canvas.draw()


def animate(i, controller, iterator):
    """
    Adapter function to map animation parameters.

    :param int i: The element from animator. It is ignored in this case.
    :param GesdReplayController controller: The GesdReplayController instance for pause handling.
    :param iterable iterator: An iterable instance for the frames (A GesdReplayMode instance).
    :return: The matplotlib artists.
    :rtype: list(matplotlib.Artist).
    """
    LOG.debug("animate", i=i, iterator=iterator)

    # on_key_press left / right may start the animator while we are still paused.
    # But we should stop the animator after each event in this case.
    if controller.pause:
        controller.animator.event_source.stop()

    return next(iterator)


# pylint: disable=too-many-arguments
def replay_gesd(command_params,
                command_config,
                standardize=False,
                show=True,
                save=False,
                ticker=False,
                sigma_range=3.0,
                interval=DEFAULT_INTERVAL,
                blit=False):
    """
    Replay the GESD output over time and display the results as a graph.

    :param ReplayGesdParams command_params: The Replay parameters for this model.
    :param CommandConfig command_config: The configuration common to all.
    :param bool standardize: If true then, for each result in the series , subtract the mean and
    divide by the standard deviation.
    :param bool show: If true then show the animation.
    :param bool save: If true then save the animation to a file.
    :param bool ticker: Animate as a ticker.
    :param float sigma_range: The number of standard deviations to show.
    :param int interval: The delay between frames (in millis).
    :param bool blit: Optimize animation.
    :see animation.FuncAnimation
    """
    LOG.debug(
        'replay_gesd',
        command_params=command_params,
        standardize=standardize,
        show=show,
        save=save,
        interval=interval,
        command_config=command_config)
    identifier_str = "{project} {variant} {task} {test} {thread_level}".format(
        **command_params.test_identifier)
    with get_matplotlib().style.context(command_config.style):
        controller = None
        try:
            LOG.info('replay_gesd', test_identifier=command_params.test_identifier)

            controller = GesdReplayController(command_params, standardize, command_config)
            controller.identifier_str = identifier_str
            controller.sigma_range = sigma_range
            controller.ticker = ticker
            controller.interval = interval
            controller.blit = blit

            if show:
                controller.show()
            if save:
                controller.save(file_format=command_config.file_format)
                controller.hide()

        except KeyError:
            LOG.error('unexpected error', exc_info=1)
            if controller is not None:
                controller.hide()
