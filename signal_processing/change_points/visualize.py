"""
Functionality to visualize change points.
*Note : this functionality is provided as is and is liable to change / break.*
"""
import functools
import json

import numpy as np
import pymongo
import scipy
import scipy.signal
import structlog

from signal_processing.commands.helpers import LANDSCAPE_FIGSIZE
from signal_processing.change_points.e_divisive import EDivisive
from signal_processing.detect_changes import PointsModel

LOG = structlog.getLogger(__name__)

DEFAULT_OUTLIER_LIMIT = 3.0
"""
The default value for outlier detection. Any zscore greater than this is an outlier.
"""


def create_format_fn(revisions, create_times):
    """
    Create a formatter function for a plot.

    :param list(str) revisions: The list of revisions.
    :param list(datetime) create_times: The list of times.
    :return: The tick string.
    """

    def format_fn(tick_val, tick_pos):
        # pylint: disable=unused-argument
        """
        Format a value on the graph.

        :param int tick_val: The value.
        :param int tick_pos: The value.
        :return: The tick string.
        """
        if int(tick_val) < len(revisions):
            i = int(tick_val)
            tick_str = revisions[i][0:7]
            if create_times and i < len(create_times):
                tick_str = tick_str + '\n' + create_times[i][0:10]
        else:
            tick_str = ''
        return tick_str

    return format_fn


def add_arrow(line, position=None, direction='right', size=15, color=None):
    """
    Add an arrow to a line.

    :param Line2D line: The line object.
    :param float position: The x-position of the arrow. If None, mean of x data is taken.
    :param str direction: 'left' or 'right'.
    :param float size: The size of the arrow in fontsize points.
    :param str color: if None, line color is taken.
    """
    if color is None:
        color = line.get_color()

    xdata = line.get_xdata()
    ydata = line.get_ydata()

    if position is None:
        position = xdata.mean()
    # find closest index
    start_ind = np.argmin(np.absolute(xdata - position))
    if direction == 'right':
        end_ind = start_ind + 1
    else:
        end_ind = start_ind - 1

    line.axes.annotate(
        '',
        xytext=(xdata[start_ind], ydata[start_ind]),
        xy=(xdata[end_ind], ydata[end_ind]),
        arrowprops=dict(arrowstyle="-|>", color=color),
        size=size)


def on_click(event, series=None, source=None):
    """
    Handle a click event and print some information about the point in question.

    :param Line2D event: The matplotlib event.
    :param dict() series: The series
    :param object source: The matplotlib object that was clicked.
    """
    if event.artist != source:
        return True

    for _, index in enumerate(event.ind):
        # pylint: disable=too-many-format-args
        text = "db.points.find({{project:'{}', variant:'{}', task: '{}', test: '{}'," \
                "revision:'{}'}})\n{}\n{}\n{}".format(series['project'],
                                                      series['variant'],
                                                      series['task'],
                                                      series['test'],
                                                      series['revisions'][index],
                                                      series['create_times'][index],
                                                      series['series'][index],
                                                      series['series'][index],
                                                      index)
        print text
    return True


def update_annotation(annotation, coordinates, index, series):
    """
    Update the hover annotation with information about the point in question.

    :param object annotation: The annotation object
    :param list(float,float) coordinates: The coordinates to annotate.
    :param int index: The index of the performance point.
    :param dict() series: The series
    """
    annotation.xy = coordinates

    text = "{}\n{}\n{}\n{}".format(series['revisions'][index], series['create_times'][index],
                                   series['series'][index], index)
    annotation.set_text(text)
    annotation.get_bbox_patch().set_facecolor('k')


# pylint: disable=too-many-arguments, too-many-locals
def on_hover(event, axis=None, annotation=None, source=None, figure=None, series=None):
    """
    Handle a hover event, update the annotation and make it visible.

    :param object event: The matplotlib event.
    :param object axis: The matplotlib axis.
    :param object annotation: The annotation object.
    :param dict series: The series,
    :param object source: The matplotlib object in focus.
    :param object figure: The matplotlib figure.
    """
    from matplotlib.lines import Line2D
    vis = annotation.get_visible()
    if event.inaxes == axis:
        cont, ind = source.contains(event)
        if cont:
            if isinstance(source, Line2D):
                line = source
                xdata = line.get_xdata()
                ydata = line.get_ydata()

                index = event['ind'][0]

                pos = (xdata[index], ydata[index])
            else:
                scatter = source
                index = ind["ind"][0]
                pos = scatter.get_offsets()[index]

            update_annotation(annotation, pos, index, series)
            annotation.set_visible(True)
            figure.canvas.draw_idle()
        else:
            if vis:
                annotation.set_visible(False)
                figure.canvas.draw_idle()


def generate_upper_lower_bounds(series, description, sigma):
    """
    Given a series and descriptive stats generate a set of values + or - sigma * standard
    deviation from each series value.

    :param list(float) series: The source data.
    :param float sigma: The number of standard deviations.
    :param tuple description: The descriptive stats.
    :return: lower and upper bounds.
    :rtype: list(float), list(float)

    see 'scipy.stats.describe'
    """
    lower_bound = series - sigma * np.sqrt(description.variance)
    upper_bound = series + sigma * np.sqrt(description.variance)
    LOG.debug(
        "after change point",
        description=description.variance,
        data=series,
        lower_bound=lower_bound,
        upper_bound=upper_bound)
    return lower_bound, upper_bound


def create_lower_upper_bounds(series, start, end, sigma):
    """
    Create a set of lower and upper bounds ranges,

    :param list(float) series: The series.
    :param int start: The start of the range.
    :param int end: The end.
    :param float sigma: The number of standard deviations.
    :return: lower, values, upper lists for the range
    """

    # Exclude first and last points as these are change points can skew the mean, variance
    # and stddev.
    array = series[start + 1:end - 1]
    description = scipy.stats.describe(array)
    values = np.repeat(description.mean, len(array) + 2)

    lower, upper = generate_upper_lower_bounds(values, description, sigma)

    LOG.debug(
        "before change point",
        description=description,
        data=values,
        lower_bound=lower,
        upper_bound=upper)

    return lower, values, upper


def on_pick_legend(figure, event, sigma_label=None, artists=None):
    """
    Handle pick event on a legend item. Toggle visibility on the matplotlib elements and set
    the alpha state of the legend item.

    :param object figure: The matplotlib figure.
    :param object event: The matplotlib event.
    :param object sigma_label: The label for the standard deviation
    :param list artists: The list of matplotlib lines.
    """
    artist = event.artist
    name = artist.get_label()
    if name in artists:
        origlines = artists[name]
        if not isinstance(origlines, list):
            origlines = [origlines]
    else:
        origlines = sigma_label
        if not isinstance(origlines, list):
            origlines = [origlines]
    for origline in origlines:
        vis = not origline.get_visible()
        origline.set_visible(vis)
        # Change the alpha on the line in the legend so we can see what lines
        # have been toggled
        if vis:
            artist.set_alpha(1.0)
        else:
            artist.set_alpha(0.2)
    figure.canvas.draw()


def plot_qhat_values(e_divisive,
                     axis,
                     series,
                     xvals,
                     revisions,
                     change_points,
                     label,
                     start=None,
                     end=None):
    # pylint: disable=too-many-locals
    """
    Given a set of precalculated change points, calculate the qhat values for
    each change point range.

    :param EDivisive e_divisive: The instance to generate the qhat values.
    :param matplotlib.axes.Axes axis: Where to draw the lines.
    :param list series: The performance data.
    :param list xvals: The x axis data.
    :param list revisions: The revisions data.
    :param list change_points: The change points (sorted by order_of_change_point).
    :param str label: The label to use when plotting the qhat values.
    :param start: The starting index for the range.  None implies the full range (0).
    :type start: int or None.
    :param end: The ending index for the range. None implies the full range (len(series)).
    :type end: int or None.
    :return: A list of the lines.
    :rtype: list(matplotlib.artist.Artist)
    """

    qhat_lines = []
    if change_points:
        current = change_points[0]
        if end is None:
            end = len(series)
        if start is None:
            start = 0

        values = e_divisive.qhat_values(series[start:end])
        line, = axis.plot(xvals[start:end], values, '1-', label=label)
        qhat_lines = [line]

        revision = current['algorithm']['revision']
        position = revisions.index(revision)

        before = [
            change_point for change_point in change_points
            if change_point['order'] < current['order']
        ]
        before_qhat_lines = plot_qhat_values(
            e_divisive,
            axis,
            series,
            xvals,
            revisions,
            before,
            label=label,
            start=start,
            end=position)
        qhat_lines += before_qhat_lines

        after = [
            change_point for change_point in change_points
            if change_point['order'] > current['order']
        ]
        after_qhat_lines = plot_qhat_values(
            e_divisive, axis, series, xvals, revisions, after, label=label, start=position, end=end)
        qhat_lines += after_qhat_lines

    return qhat_lines


def find_outliers(subseries, outlier_limit=DEFAULT_OUTLIER_LIMIT, offset=0):
    """  Given a set of data, calculate the z scores for the series and then find the indexes of
    all outliers (where abs(zscore) > outlier_limit).

    The value of the z score equals the number of standard deviations from the mean.
    So:
      * 0 implies this value is equal to the mean.
      * -1 represents an element that is 1 standard deviation less than the mean.
      * 1 represents an element that is 1 standard deviation greater than the mean.

    :param list(float) subseries: The series of data.
    :param float outlier_limit: Any abs(z score) greater than this value is an outlier.
    :param int offset: Add this value to the outlier indexes to get the real indexes in the
    containing series.

    :return: list of outlier indexes.
    :see: 'scipy.stats.zscore
        <https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.zscore.html>'
    :see: 'z-scores-review
        <https://www.khanacademy.org/math/statistics-probability/modeling-distributions-of-data/z-scores/a/z-scores-review>'
    :see: 'Z-scores
        <https://stattrek.com/statistics/dictionary.aspx?definition=z_score>'
    """
    zscores = scipy.stats.zscore(subseries)
    outliers = abs(zscores) > outlier_limit
    indexes = np.where(outliers)[0]
    indexes += offset
    return indexes


def plot_outliers(change_points,
                  series,
                  xvals,
                  revisions,
                  axis,
                  outlier_limit=DEFAULT_OUTLIER_LIMIT,
                  marker='r*'):
    """ Plot outliers on the graph.
    :param list(dict) change_points: A list of the change points.
    :param list(float) series: The performance data.
    :param list() xvals: The xaxis values.
    :param list(str) revisions: A list of the revisions.
    :param matplotlib.Axes axis: The matplotlib axis to draw on.
    :param float outlier_limit: The limit for the z score comparison.
    :param str marker: The matplotlib marker for outliers.

    :return: tuple of label, lines
    """
    outliers = np.array([], dtype=np.int32)
    previous_index = 0
    for change_point in change_points:
        suspect_revision_index = revisions.index(change_point['suspect_revision'])
        outlier_indexes = find_outliers(
            series[previous_index:suspect_revision_index],
            outlier_limit=outlier_limit,
            offset=previous_index)
        outliers = np.append(outliers, outlier_indexes)
        previous_index = suspect_revision_index

    outlier_indexes = find_outliers(
        series[previous_index:], outlier_limit=outlier_limit, offset=previous_index)
    outliers = np.append(outliers, outlier_indexes)

    label = "outliers"
    outlier_lines, = axis.plot(
        xvals[outliers], series[outliers], marker, label=label, markersize=12)

    return label, outlier_lines


def plot_change_point_ranges(change_points,
                             series,
                             xvals,
                             revisions,
                             axis,
                             sigma,
                             data,
                             lower_bound,
                             upper_bound,
                             marker='--'):
    """ Plot change point ranges on the graph.
    :param list(dict) change_points: A list of the change points.
    :param list(float) series: The performance data.
    :param list() xvals: The xaxis values.
    :param list(str) revisions: A list of the revisions.
    :param matplotlib.Axes axis: The matplotlib axis to draw on.
    :param float sigma: The std dev range to calculate the upper and lower bounds.
    :param str marker: The matplotlib marker for outliers.
    :param list data: The median line data.
    :param list lower_bound: The lower bound data (-sigma).
    :param list upper_bound: The upper bound data (+sigma)

    :return: tuple of label, lines
    """

    for change_point_index, change_point in enumerate(change_points):
        suspect_revision_index = revisions.index(change_point['suspect_revision'])
        stable_revision_index = suspect_revision_index - 1
        if 'next' in change_point['statistics']:
            next_index = suspect_revision_index + change_point['statistics']['next']['nobs']
        else:
            next_index = len(series)

        if change_point_index == 0:
            if 'previous' in change_point['statistics']:
                previous_index = stable_revision_index - \
                                 change_point['statistics']['previous']['nobs']
            else:
                previous_index = 0
            lower, values, upper = create_lower_upper_bounds(series, previous_index,
                                                             stable_revision_index, sigma)
            data[previous_index:previous_index + len(values)] = values
            lower_bound[previous_index:previous_index + len(values)] = lower
            upper_bound[previous_index:previous_index + len(values)] = upper

        lower, values, upper = create_lower_upper_bounds(series, suspect_revision_index - 1,
                                                         next_index, sigma)
        data[suspect_revision_index - 1:suspect_revision_index - 1 + len(values)] = values
        lower_bound[suspect_revision_index - 1:suspect_revision_index - 1 + len(values)] = lower
        upper_bound[suspect_revision_index - 1:suspect_revision_index - 1 + len(values)] = upper

    label = "discrete"
    discrete_lines, = axis.plot(xvals, data, marker, label=label)

    return label, discrete_lines


def plot_change_point_lines(change_points, series, revisions, axis, marker='ro-'):
    """ Plot change point lines on the graph.
    :param list(dict) change_points: A list of the change points.
    :param list(float) series: The performance data.
    :param list(str) revisions: A list of the revisions.
    :param matplotlib.Axes axis: The matplotlib axis to draw on.
    :param str marker: The matplotlib marker for outliers.

    :return: tuple of label, lines
    """
    change_point_lines = []
    label = "change"
    for change_point_index, change_point in enumerate(change_points):
        suspect_revision_index = revisions.index(change_point['suspect_revision'])
        stable_revision_index = suspect_revision_index - 1

        coordinates = (stable_revision_index, suspect_revision_index)
        if not change_point_index:
            line, = axis.plot(
                coordinates, [series[pos] for pos in coordinates], marker, label=label)
        else:
            line, = axis.plot(coordinates, [series[pos] for pos in coordinates], marker)
        change_point_lines.append(line)

    add_arrow(line, size=20)

    return label, change_point_lines


def plot_change_point_scatter(change_points, series, revisions, axis, marker='o'):
    """ Plot scatter change point on the graph.
    :param list(dict) change_points: A list of the change points.
    :param list(float) series: The performance data.
    :param list(str) revisions: A list of the revisions.
    :param matplotlib.Axes axis: The matplotlib axis to draw on.
    :param str marker: The matplotlib marker for outliers.

    :return: tuple of label, lines
    """
    label = "change points"
    change_points_indexes = [
        revisions.index(change_point['suspect_revision']) for change_point in change_points
    ]
    change_points_scatter = axis.scatter(
        change_points_indexes, [series[index] for index in change_points_indexes],
        marker=marker,
        color='k',
        s=50,
        label=label)

    return label, change_points_scatter


def plot(result,
         change_points,
         sigma,
         filter_name="butter",
         show_qhat=True,
         show_outliers=True,
         outlier_limit=DEFAULT_OUTLIER_LIMIT):
    # pylint: disable=too-many-locals, too-many-statements, too-many-branches
    """
    Plot performance and change point data.

    :param dict result: The performance data set.
    :param list(dict) change_points: A list of change points for the performance data.
    :param float sigma: The number of standard deviations to render in bounds around the lines.
    :param str filter_name: The filter to apply.
    """

    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, MaxNLocator
    thread_level = result['thread_level']
    series = np.array(result['series'], dtype=np.float64)
    revisions = result['revisions']
    create_times = result['create_times']

    labeled_items = {}
    line_labeled_items = []
    other_labeled_items = []
    pts = len(series)
    xvals = np.arange(pts)

    plot_size = 1
    figure = plt.figure(figsize=LANDSCAPE_FIGSIZE)
    title = "{project} / {variant} / {task} / {test}".format(**result)

    plt.suptitle(title, fontsize=12)
    format_fn = create_format_fn(revisions, create_times)
    axis = plt.subplot(plot_size, 1, 1)

    axis.set_ylabel('ops per sec')
    axis.set_xlabel('rev (date)')

    axis.set_title("{}".format(thread_level), size=10)
    axis.xaxis.set_major_formatter(FuncFormatter(format_fn))
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))

    for tick in axis.get_xticklabels():
        tick.set_visible(True)

    if filter_name == "butter":
        numerator, denominator = scipy.signal.butter(8, 0.125)
        try:
            yhat = scipy.signal.filtfilt(numerator, denominator, series)
        except ValueError:
            yhat = scipy.signal.filtfilt(numerator, denominator, series, padlen=0)

    else:
        window_size = len(series) / 2
        window_size = window_size - 1 if window_size % 2 == 0 else window_size
        polynomial_order = 2
        if window_size < polynomial_order:
            window_size = 3
        yhat = scipy.signal.savgol_filter(series, window_size, polynomial_order, mode='nearest')

    label = "smooth"
    smooth, = axis.plot(xvals, yhat, '-', label=label)
    line_labeled_items.append(smooth)
    labeled_items[label] = smooth

    data = np.zeros(len(series))
    lower_bound = np.zeros(len(series))
    upper_bound = np.zeros(len(series))

    if change_points:
        label, discrete_lines = plot_change_point_ranges(
            change_points, series, xvals, revisions, axis, sigma, data, lower_bound, upper_bound)
        line_labeled_items.append(discrete_lines)
        labeled_items[label] = discrete_lines
    else:

        description = scipy.stats.describe(series)

        data = yhat
        lower_bound, upper_bound = generate_upper_lower_bounds(data, description, sigma)

    if change_points and show_outliers:
        label, outlier_lines = plot_outliers(
            change_points, series, xvals, revisions, axis, outlier_limit=outlier_limit)

        line_labeled_items.append(outlier_lines)
        labeled_items[label] = outlier_lines

    if change_points and show_qhat:
        e_divisive = EDivisive(pvalue=.05)

        label = "qhat values"
        twinx = axis.twinx()
        qhat_lines = plot_qhat_values(
            e_divisive,
            twinx,
            series,
            xvals,
            revisions,
            sorted(change_points, key=lambda x: x['order_of_change_point']),
            label=label)

        line_labeled_items.extend(qhat_lines)
        labeled_items[label] = qhat_lines

    label = 'series'
    line, = axis.plot(xvals, series, '-', label=label)
    line_labeled_items.append(line)
    labeled_items[label] = line

    label = r'{} $\sigma$'.format(sigma)
    sigma_fil = axis.fill_between(xvals, lower_bound, upper_bound, alpha=0.5, label=label)
    other_labeled_items.append(sigma_fil)
    labeled_items[label] = sigma_fil

    if change_points:
        label, change_point_lines = plot_change_point_lines(change_points, series, revisions, axis)
        if change_point_lines:
            line_labeled_items.append(change_point_lines)
            labeled_items[label] = change_point_lines

        label, change_points_scatter = plot_change_point_scatter(change_points, series, revisions,
                                                                 axis)
        other_labeled_items.append(change_points_scatter)
        labeled_items[label] = change_points_scatter

    leg = axis.legend(
        [value if not isinstance(value, list) else value[0] for value in labeled_items.values()],
        labeled_items.keys(),
        loc='best',
        fancybox=True,
        shadow=True)
    leg.get_frame().set_alpha(0.4)

    color = line.get_color()
    # invisible scatter for hover but not little annoying dots.
    scatter = axis.scatter(xvals, series, marker=".", s=1, color=color, picker=5, alpha=0.7)

    annotation = axis.annotate(
        "",
        xy=(0, 0),
        xytext=(20, 20),
        textcoords="offset points",
        bbox=dict(boxstyle="round", fc="k"),
        color='w',
        arrowprops=dict(arrowstyle="-|>", color=line.get_color()))
    annotation.set_visible(False)

    figure.canvas.mpl_connect('pick_event',
                              functools.partial(on_click, series=result, source=scatter))

    figure.canvas.mpl_connect("motion_notify_event",
                              functools.partial(
                                  on_hover,
                                  axis=axis,
                                  annotation=annotation,
                                  source=scatter,
                                  figure=figure,
                                  series=result))

    for legline in leg.legendHandles:
        if legline:
            legline.set_picker(5)  # 5 pts tolerance

    figure.canvas.mpl_connect('pick_event',
                              functools.partial(
                                  on_pick_legend,
                                  figure,
                                  sigma_label=sigma_fil,
                                  artists=labeled_items))

    plt.tight_layout(pad=0.4, w_pad=0.5, h_pad=1.0, rect=[0, 0.03, 1, 0.95])
    return plt


def visualize(test_identifier,
              min_points,
              filter_name,
              command_config,
              sigma=1,
              only_change_points=True,
              show_qhat=False,
              show_outliers=False,
              outlier_limit=DEFAULT_OUTLIER_LIMIT):
    # pylint: disable=too-many-locals
    """
    Visualize the series including change points, yield the plot and thread level to the caller
    so that the calling code can decide if and how to save.

    :param tuple(str) test_identifier: The test identifier (project, variant, task test).
    :param min_points: The minimum number of points to consider when detecting change points.
    :type min_points: int or None.
    See 'PointsModel' for more information about the limit parameter.
    :param str filter_name: The scipy filters to use.
    :param CommandConfig command_config: The common command config.
    :param float sigma: The  number of standard deviations to get bounds for.
    :param bool only_change_points: Skip plots for series with no change points if set to True.
    :param bool show_qhat: Show qhat lines if set to True.
    :param bool show_outliers: Show outliers if set to True.
    :param float outlier_limit: Calculate outliers with a z score greater than this value. Default
    is 3 (standard deviations from the mean).
    :yield: The plot and thread level
    """
    LOG.debug('db.change_points.find(%s).pretty()', json.dumps(test_identifier))

    model = PointsModel(command_config.mongo_uri, min_points)
    order = model.get_closest_order(test_identifier)
    result = model.get_points(test_identifier, order)
    change_points = list(
        command_config.change_points.find(test_identifier).sort([('order', pymongo.ASCENDING)]))
    if not only_change_points or change_points:
        LOG.debug("found change points", change_points=change_points)
        yield plot(
            result,
            change_points,
            sigma,
            filter_name=filter_name,
            show_qhat=show_qhat,
            show_outliers=show_outliers,
            outlier_limit=outlier_limit)
