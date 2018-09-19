"""
Functionality to visualize change points.
*Note : this functionality is provided as is and is liable to change / break.*
"""
import functools
import json
from collections import OrderedDict

import structlog
from matplotlib.lines import Line2D
from scipy import stats, signal
from scipy.signal import savgol_filter
import numpy as np
import pymongo
from signal_processing.commands.compare import LANDSCAPE_FIGSIZE

from signal_processing.detect_changes import PointsModel

LOG = structlog.getLogger(__name__)


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


# pylint: disable=too-many-arguments
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
    array = series[start:end]
    description = stats.describe(array)
    values = np.repeat(description.mean, len(array))

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


def plot(result, sigma, filter_name="butter"):
    # pylint: disable=too-many-locals, too-many-statements, too-many-branches
    """
    Plot performance and change point data.

    :param dict result: The performance data set.
    :param float sigma: The number of standard deviations to render in bounds around the lines.
    :param str filter_name: The filter to apply.
    """

    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, MaxNLocator
    thread_level = result['thread_level']
    series = np.array(result['series'], dtype=np.float64)
    revisions = result['revisions']
    create_times = result['create_times']
    change_points = result['change_points']

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
        numerator, denominator = signal.butter(8, 0.125)
        try:
            yhat = signal.filtfilt(numerator, denominator, series)
        except ValueError:
            yhat = signal.filtfilt(numerator, denominator, series, padlen=0)

    else:
        window_size = len(series) / 2
        window_size = window_size - 1 if window_size % 2 == 0 else window_size
        polynomial_order = 2
        if window_size < polynomial_order:
            window_size = 3
        yhat = savgol_filter(series, window_size, polynomial_order, mode='nearest')

    label = "smooth"
    smooth, = axis.plot(xvals, yhat, '-', label=label)
    line_labeled_items.append(smooth)
    labeled_items[label] = smooth
    if change_points:
        data = np.zeros(len(series))
        lower_bound = np.zeros(len(series))
        upper_bound = np.zeros(len(series))

        for change_point_index, change_point in enumerate(change_points):
            # sorted(change_points, key=lambda x: x['order'])):
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
        discrete_lines, = axis.plot(xvals, data, '--', label=label)
        # discrete_lines.set_visible(False)

        line_labeled_items.append(discrete_lines)
        labeled_items[label] = discrete_lines

    else:

        description = stats.describe(series)

        data = yhat
        lower_bound, upper_bound = generate_upper_lower_bounds(data, description, sigma)

    label = 'series'
    line, = axis.plot(xvals, series, '-', label=label)
    line_labeled_items.append(line)
    labeled_items[label] = line

    label = r'{} $\sigma$'.format(sigma)
    sigma_fil = axis.fill_between(xvals, lower_bound, upper_bound, alpha=0.5, label=label)
    other_labeled_items.append(sigma_fil)
    labeled_items[label] = sigma_fil

    if change_points:
        change_point_lines = []
        label = "change"
        for change_point_index, change_point in enumerate(change_points):
            # sorted(change_points, key=lambda x: x['order'])):
            suspect_revision_index = revisions.index(change_point['suspect_revision'])
            stable_revision_index = suspect_revision_index - 1

            coordinates = (stable_revision_index, suspect_revision_index)
            if not change_point_index:
                line, = axis.plot(
                    coordinates, [series[pos] for pos in coordinates], 'ro-', label=label)
            else:
                line, = axis.plot(coordinates, [series[pos] for pos in coordinates], 'ro-')
            change_point_lines.append(line)
        if change_point_lines:
            line_labeled_items.append(change_point_lines)
            labeled_items[label] = change_point_lines

        add_arrow(line, size=20)
    if change_points:
        label = "change points"
        change_points_indexes = [
            revisions.index(change_point['suspect_revision'])
            for change_point in result['change_points']
        ]
        change_points_scatter = axis.scatter(
            change_points_indexes, [series[index] for index in change_points_indexes],
            marker="o",
            color='k',
            s=50,
            label=label)
        other_labeled_items.append(change_points_scatter)
        labeled_items[label] = change_points_scatter

    leg = axis.legend(loc='best', fancybox=True, shadow=True)
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
        legline.set_picker(5)  # 5 pts tolerance

    figure.canvas.mpl_connect('pick_event',
                              functools.partial(
                                  on_pick_legend,
                                  figure,
                                  sigma_label=sigma_fil,
                                  artists=labeled_items))

    plt.tight_layout(pad=0.4, w_pad=0.5, h_pad=1.0, rect=[0, 0.03, 1, 0.95])
    return plt


def visualize(test_identifier, filter_name, command_config, sigma=1, only_change_points=True):
    # pylint: disable=too-many-locals
    """
    Visualize the series including change points, yield the plot and thread level to the caller
    so that the calling code can decide if and how to save.

    :param tuple(str) test_identifier: The test identifier (project, variant, task test).
    :param str filter_name: The scipy filters to use.
    :param CommandConfig command_config: The common command config.
    :param float sigma: The  number of standard deviations to get bounds for.
    :param bool only_change_points: Skip plots for series with no change points if set to True.
    :yield: The plot and thread level
    """
    project = test_identifier['project']
    variant = test_identifier['variant']
    task = test_identifier['task']
    test = test_identifier['test']

    qry = {'project': project, 'variant': variant, 'task': task, 'test': test}

    LOG.debug('db.change_points.find(%s).pretty()', json.dumps(qry))
    perf_json = OrderedDict([('project_id', project), ('variant', variant), ('task_name', task)])

    model = PointsModel(perf_json, command_config.mongo_uri)
    _, query, points = model.get_points(test)
    series = points['series']
    revisions = points['revisions']
    orders = points['orders']
    create_times = points['create_times']

    thread_levels = series.keys()
    thread_levels.sort(key=int)
    for thread_level in thread_levels:
        query = OrderedDict([('project', test_identifier['project']),
                             ('variant', test_identifier['variant']),
                             ('task', test_identifier['task']),
                             ('test', test_identifier['test']),
                             ('thread_level', thread_level)]) #yapf: disable

        change_points = list(
            command_config.change_points.find(query).sort([('order', pymongo.ASCENDING)]))
        if not only_change_points or change_points:
            LOG.debug("found change points", change_points=change_points)
            result = OrderedDict([('project', test_identifier['project']),
                                  ('variant', test_identifier['variant']),
                                  ('task', test_identifier['task']),
                                  ('test', test_identifier['test']),
                                  ('thread_level', thread_level),
                                  ('series', series[thread_level]),
                                  ('revisions', revisions[thread_level]),
                                  ('orders', orders[thread_level]),
                                  ('create_times', create_times[thread_level]),
                                  ('change_points', change_points)
                                 ]) #yapf: disable

            yield plot(result, sigma, filter_name=filter_name), thread_level
