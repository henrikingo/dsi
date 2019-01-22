"""
Group of functionality to compare performance of various implementations.
"""
from __future__ import print_function

import json
import os
from datetime import datetime
from itertools import izip
from operator import itemgetter
from collections import defaultdict

import click
import numpy as np
import structlog
from scipy import stats

import signal_processing.profiling.compare_algorithms as compare_algorithms
import signal_processing.change_points.e_divisive
import signal_processing.native.e_divisive

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


def runif(execute,
          results,
          warmup,
          iterations,
          tsd,
          q_algorithm,
          windowed=False,
          implementation="P"):
    """
    Run if execute is True.

    :parameter bool execute: Execute test if this flag is True.
    :parameter list results: The list for results.
    :parameter bool warmup: Execute a warmup phase.
    :parameter int iterations: The number of iterations.
    :parameter np.array(float) tsd: Time Series data.
    :parameter object q_algorithm: The implementation.
    :parameter bool windowed: Run as windowed.
    :parameter str implementation: Indicate whether the implementation type.
    Can be 'P' for pure python, 'C' for cython or 'N' for native.
    """
    if execute:
        name = q_algorithm.__class__.__name__
        output = {'name': name, 'iterations': []}
        if warmup:
            runit(tsd, q_algorithm, windowed=windowed)
        for _ in range(iterations):
            output['iterations'].append(runit(tsd, q_algorithm, windowed=windowed))

        output['implementation'] = implementation
        output['durations'] = [iteration['duration'] for iteration in output['iterations']]
        output['min_duration'] = np.min(output['durations'])
        output['max_duration'] = np.max(output['durations'])
        output['duration'] = np.average(output['durations'])
        output['size'] = len(tsd)
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
@click.option(
    '--no-e-divisive', 'e_divisive', is_flag=True, default=True, help="Current E-Divisive.")
@click.option(
    '--original / --no-original',
    'original',
    is_flag=True,
    default=True,
    help="Original E-Divisive.")
@click.option(
    '--no-optimized-e-divisive',
    'optimized_e_divisive',
    is_flag=True,
    default=True,
    help="Optimized E-Divisive.")
@click.option(
    '--no-numpy', 'numpy_e_divisive', is_flag=True, default=True, help="Numpy E-Divisive.")
@click.option(
    '--no-numpy-optimized-e-divisive',
    'numpy_optimized_e_divisive',
    is_flag=True,
    default=True,
    help="Numpy Optimized E-Divisive.")
@click.option(
    '--windowed / --no-windowed',
    'windowed_e_divisive',
    is_flag=True,
    default=True,
    help="Windowed E-Divisive.")
@click.option(
    '--warmup / --no-warmup', 'warmup', is_flag=True, default=True, help="Run a warmup iteration")
@click.option(
    '--iterations',
    'iterations',
    default=10,
    help="Set the number of iterations. Original E-Divisive is only ever 1.")
@click.option(
    '--plot / --no-plot',
    'plot',
    default=False,
    help="Plot the series and the E-Divisive qhat values.")
@click.option(
    '--python / --no-python', 'use_python', default=True, help="Run the pure python version.")
@click.option('--cython / --no-cython', 'use_cython', default=False, help="Run the cython version.")
@click.option(
    '--short / --no-short', 'short', default=False, help="Run against a short TSD (12 elements).")
@click.option(
    '--mutable', 'mutable', is_flag=True, default=False, help="Make the np array mutable.")
@click.option(
    '--native  / --no-native',
    'native',
    is_flag=True,
    default=True,
    help="Run the native implementation.")
@click.option(
    '--fixture',
    'fixture_file_names',
    default=['perf-1635'],
    multiple=True,
    help="The default fixture filename.")
@click.option(
    '--validate / --no-validate',
    'validate',
    default=True,
    help="Validate the E-Divisive qhat values.")
@click.option(
    '--atol', 'atol', default=1.e-3, help="The max tolerance when comparing E-Divisive results.")
def cli(e_divisive, original, optimized_e_divisive, numpy_e_divisive, numpy_optimized_e_divisive,
        windowed_e_divisive, warmup, iterations, plot, use_python, use_cython, short, mutable,
        native, fixture_file_names, validate, atol):
    """
    Main driver function.
    """
    np.seterrcall(NpNullLogAdapter())
    np.seterr(all='log')

    if short:
        fixture_file_names = ['short.json']
    results = []
    expected = {}

    for fixture_file_name in fixture_file_names:
        if not fixture_file_name.endswith('.json'):
            fixture_file_name += '.json'
        fixture_path_name = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', 'change_points', 'tests',
            'unittest-files', 'e-divisive', fixture_file_name)

        fixture = load_json_file(fixture_path_name)
        series = np.array(fixture['series'], dtype=np.float)
        if 'expected' in fixture:
            expected[len(series)] = np.array(fixture['expected'], dtype=np.float)
        # else:
        #     expected = None

        if not mutable:
            series.setflags(write=False)
        np.set_printoptions(threshold=np.nan, linewidth=np.nan, precision=6)

        if use_cython:
            try:
                # pylint: disable=E1101, E0611
                import signal_processing.profiling.cython_compare_algorithms as\
                    cython_compare_algorithms
            except ImportError:
                print("no cython classes, see './README.md#Cython Variant'.")
                return

        runif(e_divisive, results, warmup, iterations, series,
              signal_processing.change_points.e_divisive.EDivisive({}))

        runif(
            windowed_e_divisive and use_python,
            results,
            warmup,
            1,
            series,
            compare_algorithms.WindowedEDivisive(),
            windowed=True)

        runif(
            windowed_e_divisive and use_python,
            results,
            warmup,
            iterations,
            series,
            compare_algorithms.NumpyWindowedEDivisive(),
            windowed=True)

        runif(optimized_e_divisive and use_python, results, warmup, iterations, series,
              compare_algorithms.OptimizedEDivisive())

        runif(numpy_optimized_e_divisive and use_python, results, warmup, iterations, series,
              compare_algorithms.NumpyOptimizedEDivisive())

        runif(numpy_e_divisive and use_python, results, warmup, iterations, series,
              compare_algorithms.NumpyEDivisive())

        runif(
            native and signal_processing.native.e_divisive.LOADED,
            results,
            warmup,
            iterations,
            series,
            compare_algorithms.NativeEDivisive(),
            implementation='N')

        runif(original and use_python, results, warmup, 1, series,
              compare_algorithms.OriginalEDivisive())

        # We need to guard against cython as you could get an Import Error.
        # leaving ```and use_cython``` in the run call in case of cut ad paste.
        if use_cython:

            # pylint: disable=E1101, E0611
            runif(
                windowed_e_divisive and use_cython,
                results,
                warmup,
                1,
                series,
                cython_compare_algorithms.WindowedEDivisive(),
                implementation='C',
                windowed=True)

            # pylint: disable=E1101, E0611
            runif(
                windowed_e_divisive and use_cython,
                results,
                warmup,
                iterations,
                series,
                cython_compare_algorithms.NumpyWindowedEDivisive(),
                implementation='C',
                windowed=True)

            # pylint: disable=E1101, E0611
            runif(
                optimized_e_divisive and use_cython,
                results,
                warmup,
                iterations,
                series,
                cython_compare_algorithms.OptimizedEDivisive(),
                implementation='C')

            runif(
                numpy_optimized_e_divisive and use_cython,
                results,
                warmup,
                iterations,
                series,
                cython_compare_algorithms.NumpyOptimizedEDivisive(),
                implementation='C')

            runif(
                numpy_e_divisive and use_cython,
                results,
                warmup,
                iterations,
                series,
                cython_compare_algorithms.NumpyEDivisive(),
                implementation='C')

            # pylint: disable=E1101, E0611
            runif(
                original and use_cython,
                results,
                warmup,
                1,
                series,
                cython_compare_algorithms.OriginalEDivisive(),
                implementation='C')

    if not results:
        click.echo('No results')
        return

    min_duration = defaultdict(lambda: float('inf'))
    min_trimmed = defaultdict(lambda: float('inf'))
    for result in results:
        size = result['size']
        min_duration[size] = min(result['duration'], min_duration[size])
        min_trimmed[size] = min(result['trimmed'], min_trimmed[size])

    # min_duration = min(result['duration'] for result in results)
    # min_trimmed = min(result['trimmed'] for result in results)
    results = sorted(results, key=itemgetter('duration'))
    print("{:>23} {:>10}  {:>10} {:>8} {:>10} {:>8} {:>14}".format("name", "size", "avg", "ratio",
                                                                   "trimmed", "ratio", "min - max"))
    print("-" * 106)
    for result in results:
        size = result['size']
        result['ratio'] = result['duration'] / min_duration[size]
        result['trimmed_ratio'] = result['trimmed'] / min_trimmed[size]

    for result in results:
        print("{name:>23} "\
              "{size:10}  {duration:10.6f}  {ratio:8.2f} "\
              "{trimmed:10.6f} {trimmed_ratio:8.2f} "\
              "{min_duration:>10.6f} {max_duration:8.6f} {0:>4} {1:>4}".format(
                  result['implementation'],
                  'RW' if mutable else 'RO',
                  **result))

    # By their nature, the windowed and non windowed implementations will have
    # different q values. So we can only compare them to the same class of
    # algorithm.

    # atol = 1.e-3
    # Get the non windowed results and compare with expected and each other.
    not_windowed = [result for result in results if not result['windowed']]
    if not_windowed and validate:
        grouped_not_windowed = defaultdict(list)
        for result in not_windowed:
            size = result['size']
            grouped_not_windowed[size].append(result)

        for size, not_windowed in grouped_not_windowed.iteritems():
            if size in expected:
                all_close = np.isclose(not_windowed[0]['qs'], expected[size], atol=atol)
                assert all(all_close), "{} != {}".format(not_windowed[0]['name'], 'expected')

            for first, second in pairwise(not_windowed):
                all_close = np.isclose(first['qs'], second['qs'], atol=atol)
                assert all(all_close), "{} != {}".format(first['name'], second['name'])

    # Get the windowed results and compare with expected and each other.
    windowed = [result for result in results if result['windowed']]

    if windowed and validate:
        grouped_windowed = defaultdict(list)
        for result in windowed:
            size = result['size']
            grouped_windowed[size].append(result)

        for size, windowed in grouped_windowed.iteritems():
            for first, second in pairwise(windowed):
                all_close = np.isclose(first['qs'], second['qs'], atol=atol)
                assert all(all_close), "{} != {}".format(first['name'], second['name'])

    if plot:
        if not_windowed:
            plot_results(series, not_windowed[0])
        if windowed:
            plot_results(series, windowed[0])
