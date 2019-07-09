#!/usr/bin/env python2.7
"""Check for performance regressions in mongo-perf project.

Example usage:
 perf_regression_check.py -f history_file.json --rev 18808cd923789a34abd7f13d62e7a73fafd5ce5f
 Loads the history json file, and looks for regressions at the revision 18808cd...
 Will exit with status code 1 if any regression is found, 0 otherwise.
"""

from __future__ import print_function
import sys
import argparse
import json
import logging

from util import read_histories, compare_one_result, log_header, read_threshold_overrides
import log_analysis
import arg_parsing

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def compare_results(  # pylint: disable=too-many-arguments,too-many-locals
        this_one,
        reference,
        threshold,
        label,
        noise_levels=None,
        noise_multiple=1,
        thread_threshold=None,
        thread_noise_multiple=None,
        using_override=None):
    '''
    Take two result series and compare them to see if they are acceptable.
    Return true if failed, and false if pass
    '''

    failed = False
    log = ""
    if not noise_levels:
        noise_levels = {}

    if not reference:
        return (failed, "No reference data for " + label)
    # Default thread_threshold to the same as the max threshold
    if not thread_threshold:
        thread_threshold = threshold
    if not thread_noise_multiple:
        thread_noise_multiple = noise_multiple

    # Check max throughput first
    noise = 0
    # For the max throughput, use the max noise across the thread levels as the noise parameter
    if noise_levels.values():
        noise = max(noise_levels.values())
    result = compare_one_result(
        this_one,
        reference,
        label,
        "max",
        noise_level=noise,
        noise_multiple=noise_multiple,
        default_threshold=threshold,
        using_override=using_override)
    log += result[1] + '\n'
    if result[0]:  # Comparison failed
        failed = True
    # Check for regression on threading levels
    thread_levels = [r for r in this_one["results"] if isinstance(this_one["results"][r], dict)]
    if len(thread_levels) > 1:
        for level in thread_levels:
            result = compare_one_result(
                this_one,
                reference,
                label,
                level,
                noise_level=noise_levels.get(level, 0),
                noise_multiple=thread_noise_multiple,
                default_threshold=thread_threshold,
                using_override=using_override)
            log += result[1] + '\n'
            if result[0]:  # Comparison failed
                failed = True

    return (failed, log)


def main(args):  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    """Main entrypoint for the script."""

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument(
        "-f", "--file", dest="file", help="path to json file containing history data")
    arg_parser.add_argument(
        "-t", "--tagFile", dest="tfile", help="path to json file containing tag data")
    arg_parser.add_argument("--rev", dest="rev", help="revision to examine for regressions")
    arg_parser.add_argument(
        "--ndays", default=7, type=int, dest="ndays", help="Check against commit from n days ago.")
    arg_parser.add_argument(
        "--threshold",
        default=0.05,
        type=float,
        dest="threshold",
        help="Don't flag an error if throughput is less than 'threshold'x100 percent off")
    arg_parser.add_argument(
        "--noiseLevel", default=1, type=float, dest="noise",
        help="Don't flag an error if throughput is less than "\
            "'noise' times the computed noise level off")
    arg_parser.add_argument(
        "--threadThreshold", default=0.1, type=float, dest="thread_threshold",
        help="Don't flag an error if thread level throughput is more than "\
             "'thread_threshold'x100 percent off")
    arg_parser.add_argument(
        "--threadNoiseLevel",
        default=2,
        type=float,
        dest="threadNoise",
        help="Don't flag an error if thread level throughput is less than 'noise' times the"
        "computed noise level off")
    arg_parser.add_argument(
        "--refTag",
        dest="reference",
        help="Reference tag to compare against. Should be a valid tag name")
    arg_parser.add_argument(
        "--overrideFile",
        dest="overrideFile",
        help="File to read for comparison override information")
    arg_parser.add_argument(
        "--variant", dest="variant", help="Variant to lookup in the override file")
    arg_parser.add_argument('--task', dest='task', help='task_name for the test in Evergreen')
    arg_parser.add_argument(
        "--out-file", help="File to write the results table to. Defaults to stdout.")
    arg_parser.add_argument(
        "--report-file",
        help='File to write the report JSON file to. Defaults to "report.json".',
        default="report.json")
    arg_parser.add_argument(
        "--is-patch",
        action='store_true',
        default=False,
        dest='is_patch',
        help='If true, will skip NDays comparison (see PERF-386).')
    # TODO: PERF-675 to remove this. Present for backwards compatibility right now.
    arg_parser.add_argument(
        "--log-analysis",
        help=("This argument is only present for backwards compatibility. To be removed."))

    arg_parsing.add_args(arg_parser, "reports analysis")

    args = arg_parser.parse_args(args)
    (history, _, overrides) = read_histories(args.variant, args.task, ofile=args.overrideFile)
    test_names = history.testnames()
    failed = 0

    results = []

    for test in test_names:  # pylint: disable=too-many-nested-blocks
        # The first entry is valid. The rest is dummy data to match the existing format
        result = {
            'test_file': test,
            'exit_code': 0,
            'elapsed': 5,
            'start': 1441227291.9624,
            'end': 1441227293.4287,
            'log_raw': ''
        }
        this_one = history.series_at_revision(test, args.rev)
        test_failed = False
        result['log_raw'] = log_header(test)

        if not this_one:
            LOGGER.info("\tno data at this revision, skipping")
            continue

        # Handle threshold overrides
        (threshold, thread_threshold, threshold_override) = read_threshold_overrides(
            test, args.threshold, args.thread_threshold, overrides)

        previous = history.series_at_n_before(test, args.rev, 1)
        if not previous:
            LOGGER.info("\tno previous data, skipping")
            continue

        using_override = []
        if threshold_override:
            using_override.append("threshold")
        cresult = compare_results(this_one, previous, threshold, "Previous",
                                  history.noise_levels(test), args.noise, thread_threshold,
                                  args.threadNoise, using_override)
        result['PreviousCompare'] = cresult[0]
        result['log_raw'] += cresult[1] + '\n'
        if cresult[0]:
            test_failed = True

        if args.out_file is None:
            print(result['log_raw'])

        if test_failed:
            result['status'] = 'fail'
            failed += 1
        else:
            result['status'] = 'pass'
        results.append(result)

    if args.reports_analysis is not None:
        log_analysis_results, _ = log_analysis.analyze_logs(args.reports_analysis, args.perf_file)
        results.extend(log_analysis_results)

    if args.out_file is not None:
        with open(args.out_file, "w") as out_file:
            for result in results:
                out_file.write(result["log_raw"])

    report = {}
    report['failures'] = failed
    report['results'] = results

    with open(args.report_file, "w") as report_file:
        json.dump(report, report_file, indent=4, separators=(',', ': '))
    return 1 if failed > 0 else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
