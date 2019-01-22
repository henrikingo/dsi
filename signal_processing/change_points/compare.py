"""
Functionality to compare R v Py change point generation.
"""
import itertools
import os
from datetime import datetime

import numpy as np
import structlog

from bin.common.utils import mkdir_p
from signal_processing.commands.helpers import PORTRAIT_FIGSIZE
from signal_processing.detect_changes import PointsModel
from signal_processing.change_points.e_divisive import EDivisive

LOG = structlog.getLogger(__name__)


def load_e_divisive():
    """
    Load rpy2, R Language and ecp.

    :return: e_divisive function
    :rtype: (function, None)
    """
    try:
        from rpy2.rinterface import RRuntimeError  # pylint: disable=unused-variable
        LOG.debug("r2py installed")

        from rpy2 import robjects
        from rpy2.robjects import Vector
        from rpy2.robjects.packages import importr
        LOG.debug("r lang installed")

        e_divisive = importr('ecp').e_divisive  # pylint: disable=no-member

        def r_vector_to_list(key,
                             value,
                             keys=('order_found', 'estimates', 'considered_last', 'permutations')):
            """
            Convert an r vector to list.

            :param str key: The key name.
            :param value: The value to convert. A vector is always converted to a list. The
            list elements are converted to int if 'key' in 'keys'.
            :type value: obj, Vector.
            :param list(str) keys: Convert to list it this is a vector. Convert list elements to
            int if key' in 'keys'.
            :return: A list of float or int if value is a vector. Otherwise the passed in value.
            :rtype: list(int), list(float) or value.
            """
            if isinstance(value, Vector):
                if key in keys:
                    value = [int(f) for f in value]
                else:
                    value = list(value)
            return value

        def calc_e_divisive(series, sig_lvl, minsize, max_permutations=100):
            """
            Calculate the change points with R ecp.
            :param list(float) series: The performance data.
            :param float sig_lvl: The level at which to sequentially test if a proposed change
            point is statistically significant.
            :param int minsize: The Minimum number of observations between change points..
            :param int max_permutations: The maximum number of random permutations to use in each
            iteration of the permutation test.

            see `ecp<https://www.rdocumentation.org/packages/ecp/versions/3.1.0/topics/e.divisive>'
            :return: raw output and generated point.
            :rtype: (dict, list(int))
            """
            # pylint: disable=no-member
            raw = e_divisive(
                X=robjects.r.matrix(series), sig_lvl=sig_lvl, min_size=minsize, R=max_permutations)
            results = dict(zip([name.replace('.', '_') for name in raw.names], list(raw)))

            limits = [1, len(series) + 1]
            # always remove first and last.
            # Additionally, r array index from 1 so decrement the value by 1
            raw = {k: r_vector_to_list(k, v) for k, v in results.items()}
            points = [int(point) - 1 for point in results['order_found'] if point not in limits]
            return raw, points

        LOG.debug("ecp installed")
    except:  # pylint: disable=bare-except
        calc_e_divisive = None
        LOG.warn("no e devisive", exc_info=1)
    return calc_e_divisive


def best_fit(x_values, y_values):
    """
    Given a list of x and y values compute the best fit line.

    To generate a line from -5 to 5 use the following code:

        import matplotlib.pyplot as plt
        from matplotlib import style
        style.use('ggplot')

        xs = range(-5, 6]
        ys = [(slope*x)+intercept for x in range(-5, 6]

        slope, intercept = best_fit(xs, ys)

        line = [(slope*x)+intercept for x in xs]
        plt.scatter(xs,ys,color='g')
        plt.plot(xs, line)
        plt.show()

    The equation is defined here http://mathworld.wolfram.com/LeastSquaresFitting.html,
    look at equations 27 and 28.

    :param x_values: A list of x values.
    :param y_values: A list of y values.
    :return: (float, float) the slope and intercept.
    """
    x_values = np.array(x_values, dtype=np.float64)
    y_values = np.array(y_values, dtype=np.float64)
    slope = (((np.mean(x_values) * np.mean(y_values)) - np.mean(x_values * y_values)) /
             ((np.mean(x_values) * np.mean(x_values)) - np.mean(x_values * x_values)))
    intercept = np.mean(y_values) - slope * np.mean(x_values)
    return slope, intercept


def print_result(result, command_config):
    # pylint: disable=line-too-long
    """
    Print a result comparison. The output will look something like the following:

	 127 105_1c_avg_latency                         4  10 0.62   7    [37] [37]                                [(37, u'fcf41c')]
	  22 105_1c_avg_latency                        32  10 0.04   2    [12] [12]                                [(12, u'cae95a')]
	 126 105_1c_avg_latency                        60  10 0.90   9    [37, 73, 85] [37, 73, 85]                [(73, u'4cee07'), (37, u'fcf41c'), (85, u'2a86ca')]
	 127 105_1c_max_latency                         4  10 0.64   8    [37] [37]                                [(37, u'fcf41c')]
	  22 105_1c_max_latency                        32  10 0.04   3    [12] [12]                                [(12, u'cae95a')]
	 126 105_1c_max_latency                        60  10 0.93   6    [37, 73, 93] [37, 73, 93]                [(73, u'4cee07'), (37, u'fcf41c'), (93, u'8678e9')]
	 127 15_1c_avg_latency                          4  10 0.60   8    [56] [58]                                [(56, u'bbe227'), (58, u'11d837')]

    Column 1: number of points in the series.
    Column 2: test name.
    Column 3: thread level.
    Column 4: minsize.
    Column 5: time taken to generate python points in seconds.
    Column 6: ratio of python time to r time taken (ie. how many times slower is python).
    Column 7: py change points.
    Column 8: r change points.
    Column 9: map of indexes to revisions.

    :param dict result: The E-Divisive and R change point results.
    :param CommandConfig command_config: The common command configuration.
    """
    # pylint:enable=line-too-long
    test = result['test']
    thread_level = result['thread_level']
    revisions = result['revisions']
    if command_config.dry_run:
        print "\t{:4} {:60} {:<40} {}".format(
            len(result['series']), "{} {}".format(test, thread_level), '', 'dry run')
    else:
        python_points = result['python_points'].points
        python_time_taken = result['python_points'].time_taken

        # multiple sets of values can be generated if multiple minsizes are provided
        all_r_points = result['r_points']
        if python_points or any(r_points.points for r_points in all_r_points):
            m = [(i, revisions[i][0:6])
                 for i in set(python_points).union(*(points.points for points in all_r_points))]
            for r_points in all_r_points:
                if r_points.e_divisive:
                    points = r_points.points
                else:
                    points = 'ecp unavailable'

                time_taken_ratio = python_time_taken / r_points.time_taken
                print "\t{:4} {:60} {:<40} {}".format(
                    len(result['series']), "{:40} {:>3} {:>3} {:.2f} {:>3}".format(
                        test, thread_level, r_points.minsize, python_time_taken,
                        int(time_taken_ratio)), "{} {}".format(python_points, points), m)


# pylint: disable=too-many-instance-attributes
class ChangePointImpl(object):
    """
    Base class for Change points implementation.
    """

    # pylint: disable=too-many-arguments
    def __init__(self, data, sig_lvl, minsize, weighting, mongo_repo, credentials=None):
        """
        Create a change points generation class.

        :param dict data: The raw data.
        :param float sig_lvl: The significance level test.
        :param int minsize: The minimum distance between change points.
        :param float weighting: The value to use to generate the weightings.
        :param str mongo_repo: The github repo.
        :param dict credentials: The github credentials.

        See 'weights.DEFAULT_WEIGHTING' for the recommended default value.
        """
        self.data = data
        self.sig_lvl = sig_lvl
        self.weighting = weighting
        self.minsize = minsize
        self._points = None
        self._time_taken = None
        self.mongo_repo = mongo_repo
        self.credentials = credentials

    def _calculate(self):
        """
        Calculate the change points.
        """
        # pylint: disable=notimplemented-raised, not-callable, no-self-use
        raise NotImplemented("implement me")

    @property
    def points(self):
        """
        Get the points. This is lazy evaluated.

        :return: list(int).
        """
        if self._points is None:
            start = datetime.now()
            self._calculate()
            time_taken = datetime.now() - start
            self._time_taken = time_taken.total_seconds()
            LOG.debug(
                "points: calculate",
                took=self._time_taken,
                name=type(self).__name__,
                len=len(self.data['series']))
        return self._points

    @property
    def raw(self):
        """
        Get the raw result.

        :return: None for most classes.
        """
        return None

    @property
    def time_taken(self):
        """
        Get the number of seconds taken to calculate the points. The value returned is a float in
        microsecond accuracy.
        see :method: `timedelta.total_seconds`.

        :return: The amount of time taken to calculate the change points.
        :rtype: float.
        """
        if self._time_taken is None:
            # _ = .. otherwise lint error
            _ = self.points
        return self._time_taken


class RChangePoint(ChangePointImpl):
    """
    Class to encapsulate R change Point generation.
    """

    def __init__(self, *args, **kwargs):
        """
        Create an R change points generation class.

        :param list(obj) args: The arguments.
        :param dict(str, obj) kwargs: The keyword arguments.
        """
        ChangePointImpl.__init__(self, *args, **kwargs)
        self._raw = None
        self._ecp = None
        self.e_divisive = load_e_divisive()

    def _calculate(self):
        """
        Calculate the change points.

        :return: list(int).
        """
        if self.e_divisive:
            raw, points = self.e_divisive(
                self.data['series'], sig_lvl=self.sig_lvl, minsize=self.minsize)
            self._raw = raw
            self._points = points
        else:
            self._raw = {}
            self._points = []

    @property
    def raw(self):
        """
        Get the raw result. This is lazy evaluated.

        :return: dict.
        """
        if self._points is None:
            self._calculate()
        return self._raw


class PyChangePoint(ChangePointImpl):
    """
    Class to encapsulate Py change Point generation.
    """

    def _calculate(self):
        """
        Calculate the change points.

        :return: list(int).
        """
        change_points = EDivisive(
            self.data,
            pvalue=self.sig_lvl,
            weighting=self.weighting,
            mongo_repo=self.mongo_repo,
            credentials=self.credentials).change_points

        self._points = [
            self.data['revisions'].index(change_point['suspect_revision'])
            for change_point in change_points
        ]


def plot_test(save,
              show,
              test_identifier,
              results,
              padding,
              sig_lvl,
              minsizes,
              out_dir="/tmp",
              file_format="png"):
    # pylint: disable=too-many-arguments,too-many-locals
    """
    Plot a test with change points.

    :param bool save: Save the plot to a file (can be used with / without show).
    :param bool show: Show the plot to a file (can be used with / without save).
    :param tuple(str) test_identifier: Tuple containing project, variant, task, test values.
    :param ChangePointImp results: The change point calculations.
    :param int padding: The padding appended to the data.
    :param str out_dir: The location to write the output to. Defaults to /tmp.
    :param str file_format: The format to write the output to. Defaults to png.
    """
    import matplotlib.pyplot as plt
    plot_size = len(results)
    plt.figure(figsize=PORTRAIT_FIGSIZE)  # for portrait
    project, variant, task, test = test_identifier
    title = "{project} / {variant} / {task} / {test}\n{sig_lvl}".format(
        project=project, variant=variant, task=task, test=test, sig_lvl=sig_lvl)

    plt.suptitle(title, fontsize=12)
    for idx, result in enumerate(results):
        python_points = result['python_points']
        r_points = result['r_points']
        axes = plt.subplot(plot_size, 1, idx + 1)
        plot(python_points.points, r_points, result, axes=axes)
        plt.tight_layout(pad=0.4, w_pad=0.5, h_pad=1.0, rect=[0, 0.03, 1, 0.95])
    if save:
        pathname = os.path.join(out_dir, project, variant, task)
        mkdir_p(pathname)

        filename = "{test}-{minsize}-{sig_lvl}-{padding}.{file_format}".format(
            test=test,
            minsize="_".join(str(minsize) for minsize in minsizes),
            padding=padding,
            sig_lvl=sig_lvl,
            file_format=file_format)

        full_filename = os.path.join(pathname, filename)
        print "saving to {}".format(full_filename)
        plt.savefig(full_filename)
    if show:
        plt.show()
    plt.close()


def plot(python_points, r_points, result, axes):
    # pylint: disable=too-many-locals
    """
    Plot a result.

    :param list(int) python_points: The py change points.
    :param list(int) r_points: The R change points.
    :param dict result: The task result.
    :param dict result: The task result.
    :param obj axes: The axes to draw on.
    """
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    thread_level = result['thread_level']
    series = np.array(result['series'], dtype=np.float64)
    revisions = result['revisions']
    create_times = result['create_times']

    pts = len(series)
    xvals = [i for i in range(pts)]

    def format_fn(tick_val, tick_pos):
        # pylint: disable=unused-argument
        """
        Format a value on the graph.

        :param int tick_val: The value.
        :param int tick_pos: The tick pos.
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

    title = "threads: {threads}".format(threads=thread_level)

    axes.set_title(title, size=16)
    axes.set_ylabel('ops per sec')

    axes.xaxis.set_major_formatter(FuncFormatter(format_fn))
    axes.xaxis.set_major_locator(MaxNLocator(integer=True))

    for tick in axes.get_xticklabels():
        tick.set_visible(True)

    all_py_points = set(python_points)
    all_r_points = set(r_points[0].points).union(*[points.points for points in r_points])
    common = all_py_points.intersection(all_r_points)

    common_r_points = set(r_points[0].points) \
                          .intersection(*[points.points for points in r_points]) - common

    py_only = all_py_points.difference(all_r_points)
    r_only = all_r_points.difference(all_py_points)

    if common:
        axes.scatter(
            list(common), [series[pt] for pt in common],
            color="r",
            marker="+",
            s=100,
            label="common")
    if common_r_points and len(r_points) > 1:
        axes.scatter(
            list(common_r_points), [series[pt] for pt in common_r_points],
            color="g",
            marker="+",
            s=100,
            label="common r")

    if py_only:
        axes.scatter(
            list(py_only), [series[pt] for pt in py_only], color="r", marker=".", s=100, label="py")

    if r_only:
        colors = itertools.cycle('cmybwrgb')
        for points in r_points:
            uniq = set(points.points).intersection(r_only)
            if uniq:
                axes.scatter(
                    list(uniq), [series[pt] for pt in uniq],
                    color=next(colors),
                    marker="<",
                    s=100,
                    label="r{}".format(points.minsize))

    axes.plot(xvals, series, 'b-')

    axes.legend(loc="upper left")


def compare(test_identifier,
            min_points,
            command_config,
            weighting,
            sig_lvl=0.05,
            minsizes=(20, ),
            padding=0):
    # pylint: disable=too-many-locals, too-many-arguments
    """
    Calculate change points for comparison.

    :param dict() test_identifier: The test identifier (project, variant, task test).
    :param min_points: The minimum number of points to consider when detecting change points.
    :type min_points: int or None.
    See 'PointsModel' for more information about the limit parameter.
    :param CommandConfig command_config: The common command config.
    :param float sig_lvl: The significance level test.
    :param list(int) minsizes: The minimum distance between change points.
    :param int padding: Pad out the series with an extra padding amount of the last result.
    :param float weighting: The value to use to generate the weightings.
    :return: list(calculations).
    See 'weights.DEFAULT_WEIGHTING' for the recommended default value.
    """
    credentials = command_config.credentials
    mongo_repo = command_config.mongo_repo

    model = PointsModel(
        command_config.mongo_uri,
        min_points=min_points,
        mongo_repo=mongo_repo,
        credentials=credentials)
    order = model.get_closest_order(test_identifier)
    results = model.get_points(test_identifier, order)
    if padding:
        values = [results['series'][-1]] * padding
        results['series'].extend(values)

        values = [results['revisions'][-1]] * padding
        results['revisions'].extend(values)

        start = results['orders'][-1] + 1
        values = list(range(start, start + padding))
        results['orders'].extend(values)

        values = [results['create_times'][-1]] * padding
        results['create_times'].extend(values)

    results['python_points'] = PyChangePoint(
        results,
        sig_lvl,
        minsizes[0],
        weighting=weighting,
        mongo_repo=mongo_repo,
        credentials=credentials)
    results['r_points'] = [
        RChangePoint(
            results,
            sig_lvl,
            minsize,
            weighting=weighting,
            mongo_repo=mongo_repo,
            credentials=credentials) for minsize in minsizes
    ]

    return results
