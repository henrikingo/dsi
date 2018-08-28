"""
Group of functionality to compare performance of various implementations.
"""
from __future__ import print_function

import json
import os
from datetime import datetime
from itertools import izip
from operator import itemgetter

import click
import numpy as np
import structlog
from scipy import stats

import signal_processing.profiling.compare_algorithms as compare_algorithms
import signal_processing.qhat

LOG = structlog.getLogger(__name__)


def load_json_file(filename):
    """
    Load json from file.

    :parameter str filename: The json file name.
    """

    with open(filename, 'r') as json_file:
        return json.load(json_file)


def plot_results(series, results, style=('bmh', )):
    """
    Plot the series and results.

    :parameter list(float) series: Time series data.
    :parameter dict results: The results.
    """
    if results:
        import matplotlib.pyplot as plt
        with plt.style.context(style):
            name = results['name']
            qhat_values = results['qs']
            _, ax1 = plt.subplots()
            plt.suptitle('{}: {} s'.format(name, results['duration']))

            position = np.argmax(qhat_values)
            x_values = range(len(series))
            ax1.plot(x_values, qhat_values, 'r-')

            ax2 = ax1.twinx()
            ax2.plot(x_values, series, 'b--')
            plt.axvline(x=position)
            plt.show()


def pairwise(iterable):
    """
    Generate a pairwise iterator.

    :parameter iter iterable: The iterable.
    """
    i = iter(iterable)
    return izip(i, i)


class NpNullLogAdapter(object):
    """
    Adapter structlog to numpy err handler.
    """

    def write(self, msg):
        """
        Write a message.

        :param str msg: The message.
        """
        # LOG.warn(msg)
        pass


class NpWarnLogAdapter(object):
    """
    Adapter structlog to numpy err handler.
    """

    def write(self, msg):
        """
        Write a warning message.

        :param str msg: The message.
        """
        LOG.warn(msg)


def runit(tsd, q_algorithm, windowed=False):
    """
    Run a single iteration.

    :parameter object q_algorithm: The implementation.
    :parameter np.array(float) tsd: Time series data.
    :parameter bool windowed: Call a windowed implementation.
    """
    output = {'name': q_algorithm.__class__.__name__}
    start = datetime.utcnow()
    if not windowed:
        output['qs'] = q_algorithm.qhat_values(tsd)
    else:
        output['qs'] = q_algorithm.qhat_values(tsd, window=int(round(len(tsd) / 2)))
    duration = (datetime.utcnow() - start).total_seconds()
    output['duration'] = duration
    return output


def runif(execute, results, warmup, iterations, tsd, q_algorithm, is_cython=False, windowed=False):
    """
    Run if execute is True.

    :parameter bool execute: Execute test if this flag is True.
    :parameter list results: The list for results.
    :parameter bool warmup: Execute a warmup phase.
    :parameter int iterations: The number of iterations.
    :parameter np.array(float) tsd: Time Series data.
    :parameter object q_algorithm: The implementation.
    :parameter bool is_cython: The cython flag.
    :parameter bool windowed: Run as windowed.
    """
    if execute:
        name = q_algorithm.__class__.__name__
        output = {'name': name, 'iterations': []}
        if warmup:
            runit(tsd, q_algorithm, windowed=windowed)
        for _ in range(iterations):
            output['iterations'].append(runit(tsd, q_algorithm, windowed=windowed))

        output['cython'] = is_cython
        output['durations'] = [iteration['duration'] for iteration in output['iterations']]
        output['min_duration'] = np.min(output['durations'])
        output['max_duration'] = np.max(output['durations'])
        output['duration'] = np.average(output['durations'])
        if output['durations'] and len(output['durations']) > 1:
            output['description'] = stats.describe(output['durations'])
            output['trimmed'] = stats.trim_mean(output['durations'], 0.1)
        else:
            output['trimmed'] = output['duration']

        for first, second in pairwise(iteration['qs'] for iteration in output['iterations']):
            all_close = np.isclose(first, second)
            assert all(all_close), "{} != {}".format(name, 'expected')
        output['qs'] = output['iterations'][0]['qs']
        output['windowed'] = windowed

        results.append(output)


@click.command(name='cli')
@click.option('--no-qhat', 'qhat', is_flag=True, default=True, help="Original QHat.")
@click.option(
    '--no-optimized-qhat', 'optimized_qhat', is_flag=True, default=True, help="Optimized QHat.")
@click.option('--no-numpy', 'numpy_qhat', is_flag=True, default=True, help="Numpy QHat.")
@click.option(
    '--no-numpy-optimized-qhat',
    'numpy_optimized_qhat',
    is_flag=True,
    default=True,
    help="Numpy Optimized QHat.")
@click.option(
    '--windowed / --no-windowed',
    'windowed_qhat',
    is_flag=True,
    default=True,
    help="Windowed QHat.")
@click.option(
    '--warmup / --no-warmup', 'warmup', is_flag=True, default=True, help="Run a warmup iteration")
@click.option(
    '--iterations',
    'iterations',
    default=10,
    help="Set the number of iterations. Original QHat is only ever 1.")
@click.option(
    '--plot / --no-plot', 'plot', default=False, help="Plot the series and the qhat values.")
@click.option(
    '--python / --no-python', 'use_python', default=True, help="Run the pure python version.")
@click.option('--cython / --no-cython', 'use_cython', default=False, help="Run the cython version.")
@click.option(
    '--short / --no-short', 'short', default=False, help="Run against a short TSD (12 elements).")
@click.option(
    '--mutable', 'mutable', is_flag=True, default=False, help="Make the np array mutable.")
def cli(qhat, optimized_qhat, numpy_qhat, numpy_optimized_qhat, windowed_qhat, warmup, iterations,
        plot, use_python, use_cython, short, mutable):
    """
    Main driver function.
    """
    np.seterrcall(NpNullLogAdapter())
    np.seterr(all='log')

    if short:
        series = np.array([1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3], dtype=np.float)
        expected = np.array(
            [
                0, 0, 1.3777777777777778, 3.4444444444444438, 4.428571428571429, 2.971428571428571,
                3.599999999999999, 2.342857142857143, 2.857142857142857, 4.666666666666666, 0, 0
            ],
            dtype=np.float)
    else:
        fixture_file_name = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'tests', 'unittest-files', 'qhat',
            'perf-1635.json')
        fixture = load_json_file(fixture_file_name)
        series = np.array(fixture['series'], dtype=np.float)
        expected = np.array(fixture['expected'], dtype=np.float)

    if not mutable:
        series.setflags(write=False)
        expected.setflags(write=False)
    np.set_printoptions(threshold=np.nan, linewidth=np.nan, precision=6)

    results = []

    if use_cython:
        try:
            # pylint: disable=E1101, E0611
            import signal_processing.profiling.cython_compare_algorithms as\
                cython_compare_algorithms
        except ImportError:
            print("no cython classes, see './README.md#Cython Variant'.")
            return

    # run python tests first as they are always available
    # import signal_processing.qhat
    # import signal_processing.profiling.compare_algorithms as compare_algorithms

    runif(True, results, warmup, iterations, series, signal_processing.qhat.QHat({}))

    runif(
        windowed_qhat and use_python,
        results,
        warmup,
        1,
        series,
        compare_algorithms.WindowedQHat(),
        windowed=True)

    runif(
        windowed_qhat and use_python,
        results,
        warmup,
        iterations,
        series,
        compare_algorithms.NumpyWindowedQHat(),
        windowed=True)

    runif(optimized_qhat and use_python, results, warmup, iterations, series,
          compare_algorithms.OptimizedQHat())

    runif(numpy_optimized_qhat and use_python, results, warmup, iterations, series,
          compare_algorithms.NumpyOptimizedQHat())

    runif(numpy_qhat and use_python, results, warmup, iterations, series,
          compare_algorithms.NumpyQHat())

    runif(qhat and use_python, results, warmup, 1, series, compare_algorithms.OriginalQHat())

    # We need to guard against cython as you could get an Import Error.
    # leaving ```and use_cython``` in the run call in case of cut ad paste.
    if use_cython:

        # pylint: disable=E1101, E0611
        runif(
            windowed_qhat and use_cython,
            results,
            warmup,
            1,
            series,
            cython_compare_algorithms.WindowedQHat(),
            is_cython=True,
            windowed=True)

        # pylint: disable=E1101, E0611
        runif(
            windowed_qhat and use_cython,
            results,
            warmup,
            iterations,
            series,
            cython_compare_algorithms.NumpyWindowedQHat(),
            is_cython=True,
            windowed=True)

        # pylint: disable=E1101, E0611
        runif(
            optimized_qhat and use_cython,
            results,
            warmup,
            iterations,
            series,
            cython_compare_algorithms.OptimizedQHat(),
            is_cython=True)

        runif(
            numpy_optimized_qhat and use_cython,
            results,
            warmup,
            iterations,
            series,
            cython_compare_algorithms.NumpyOptimizedQHat(),
            is_cython=True)

        runif(
            numpy_qhat and use_cython,
            results,
            warmup,
            iterations,
            series,
            cython_compare_algorithms.NumpyQHat(),
            is_cython=True)

        # pylint: disable=E1101, E0611
        runif(
            qhat and use_cython,
            results,
            warmup,
            1,
            series,
            cython_compare_algorithms.OriginalQHat(),
            is_cython=True)

    if not results:
        click.echo('No results')
        return

    min_duration = min(result['duration'] for result in results)
    min_trimmed = min(result['trimmed'] for result in results)
    results = sorted(results, key=itemgetter('duration'))
    print("{:>20} {:>10} {:>8} {:>10} {:>8} {:>14}".format("name", "avg", "ratio", "trimmed",
                                                           "ratio", "min - max"))
    print("-" * 80)
    for result in results:
        result['ratio'] = result['duration'] / min_duration
        result['trimmed_ratio'] = result['trimmed'] / min_trimmed

    for result in results:
        print("{name:>20} "\
              "{duration:10.6f}  {ratio:8.2f} "\
              "{trimmed:10.6f} {trimmed_ratio:8.2f} "\
              "{min_duration:>10.6f} {max_duration:8.6f} {0:>4} {1:>4}".format(
                  'C' if result['cython'] else 'P',
                  'RW' if mutable else 'RO',
                  **result))

    # By their nature, the windowed and non windowed implementations will have
    # different q values. So we can only compare them to the same class of
    # algorithm.

    # Get the non windowed results and compare with expected and each other.
    not_windowed = [result for result in results if not result['windowed']]
    if not_windowed:
        all_close = np.isclose(not_windowed[0]['qs'], expected)
        assert all(all_close), "{} != {}".format(not_windowed[0]['name'], 'expected')

        for first, second in pairwise(not_windowed):
            all_close = np.isclose(first['qs'], second['qs'])
            assert all(all_close), "{} != {}".format(first['name'], second['name'])

    # Get the windowed results and compare with expected and each other.
    windowed = [result for result in results if result['windowed']]

    if windowed:
        for first, second in pairwise(windowed):
            all_close = np.isclose(first['qs'], second['qs'])
            assert all(all_close), "{} != {}".format(first['name'], second['name'])

    if plot:
        if not_windowed:
            plot_results(series, not_windowed[0])
        if windowed:
            plot_results(series, windowed[0])
