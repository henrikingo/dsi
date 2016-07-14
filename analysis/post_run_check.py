#!/usr/bin/env python2.7
"""
Example usage:
post_run_check.py -f history_file.json --rev 18808cd923789a34abd7f13d62e7a73fafd5ce5f
        --project_id $pr_id --variant $variant
Loads the history json file, and looks for regressions at the revision 18808cd...
Evergreen project_id and variant are used to uniquely identify the rule set to use
Will exit with status code 1 if any regression is found, 0 otherwise.
"""

from __future__ import print_function
import sys
import argparse
import json
import StringIO
import logging

from datetime import timedelta
from dateutil import parser as date_parser

from util import read_histories, compare_one_result, log_header, read_threshold_overrides
import log_analysis

logging.basicConfig(level=logging.INFO)

# Rules section - types of rules are:
# 1. Common regression rules
# 2. Additional checks that look for failures or other undesirable conditions
# 3. Project specific rules, which calls rules of types 1 & 2
#    with project-specific rule sets and thresholds/parameters


# Common regression rules

def compare_to_previous(test, threshold, thread_threshold):
    """Compare against the performance data from the previous run."""

    previous = history.series_at_n_before(test['name'], test['revision'], 1)
    if not previous:
        print("        no previous data, skipping")
        return {'PreviousCompare': 'pass'}
    else:
        return {'PreviousCompare': compare_throughputs(
            test, previous, "Previous", threshold, thread_threshold)}

def compare_to_n_days(test, threshold, thread_threshold):
    """check if there is a regression in the last week"""

    daysprevious = history.series_at_n_days_before(test['name'], test['revision'], 7)
    if not daysprevious:
        print("        no reference data for test {} with NDays".format(test['name']))
        return {}
    using_override = []
    if test['name'] in overrides['ndays']:
        try:
            override_time = date_parser.parse(overrides['ndays'][test['name']]['create_time'])
            this_time = date_parser.parse(test['create_time'])
            # I hate that this 7 is a constant. Copying constant from first line in function
            if (override_time < this_time) and ((override_time + timedelta(days=7)) >= this_time):
                daysprevious = overrides['ndays'][test['name']]
                using_override.append("reference")
            else:
                print("Out of date override found for ndays. Not using")
        except KeyError as err:
            err_msg = ("Key error accessing overrides for ndays. "
                       "Key {0} doesn't exist for test {1}").format(str(err), test['name'])
            print(err_msg, file=sys.stderr)

    return {'NDayCompare': compare_throughputs(test, daysprevious,
                                               "NDays", threshold,
                                               thread_threshold,
                                               using_override)}

def compare_to_tag(test, threshold, thread_threshold):
    """Compare against the tagged performance data in `tag_history`."""

    # if tag_history is undefined, skip this check completely
    if tag_history:
        reference = tag_history.series_at_tag(test['name'], test['ref_tag'])
        if not reference:
            print("        no reference data for test {} with baseline".format(test['name']))
            return {}
        using_override = []
        if test['name'] in overrides['reference']:
            using_override.append("reference")
            reference = overrides['reference'][test['name']]
        return {'BaselineCompare': compare_throughputs(test,
                                                       reference,
                                                       "Baseline",
                                                       threshold,
                                                       thread_threshold,
                                                       using_override)}
    else:
        return {}


# Failure and other condition checks
def replica_lag_check(test, threshold):
    """
    Iterate through all thread levels and flag a test if its max replication lag is higher
    than the threshold.
    """
    status = 'pass'
    total_lag_entry = 0
    for level in test['results']:
        lag_entry = 0
        if 'replica_avg_lag' in test['results'][level]:
            avg_lag = test['results'][level]['replica_avg_lag']
            lag_entry += 1
        else:
            avg_lag = "NA"
        if 'replica_max_lag' in test['results'][level]:
            max_lag = test['results'][level]['replica_max_lag']
            lag_entry += 1
        else:
            max_lag = "NA"
        if 'replica_end_of_test_lag' in test['results'][level]:
            end_of_test_lag = test['results'][level]['replica_end_of_test_lag']
            lag_entry += 1
        else:
            end_of_test_lag = "NA"
        total_lag_entry += 1
        # mark the test failed if max_lag is higher than threshold
        if max_lag != "NA":
            if float(max_lag) > threshold:
                status = 'fail'
                print("   ---> replica_max_lag (%s) > threshold(%s) seconds at %s" %
                      (max_lag, threshold, level))
        # print an etry in the replica_lag summary table, regardless of pass/fail
        if lag_entry > 0:
            replica_lag_line.append((test['name'], level, avg_lag, max_lag, end_of_test_lag))

    if total_lag_entry == 0:
        # no lag information
        return {}
    if status == 'pass':
        print("        replica_lag under threshold ({}) seconds".format(threshold))
    return {'Replica_lag_check': status}



# project-specific rules

def sys_windows_1_node_repl_set(test):
    """Rules for a 1-node replica set on Windows."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_n_days(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    return to_return

def sys_windows_standalone(test):
    """Rules for a standalone setup on Windows."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_n_days(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    return to_return

def sys_linux_1_node_repl_set(test):
    """Rules for a 1-node replicate set on Linux."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_n_days(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    return to_return

def sys_linux_standalone(test):
    """Rules for a standalone setup on Linux."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_n_days(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    return to_return

def sys_linux_3_shard(test):
    """Rules for a 3-shard setup on Linux."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_n_days(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    # max_lag check
    to_return.update(replica_lag_check(test, threshold=10))
    # possibly some check on whether load is balanced across shard
    return to_return

def sys_linux_3_node_repl_set(test):
    """Rules for a 3-node replica set on Linux."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_n_days(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    # max_lag check
    to_return.update(replica_lag_check(test, threshold=10))
    return to_return

def sys_linux_3_node_repl_set_isync(test):
    """Rules for a 3-node replica set on Linux."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_n_days(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    # max_lag check
    to_return.update(replica_lag_check(test, threshold=10))
    return to_return

def sys_linux_oplog_compare(test):
    """Rules for an oplog setup on Linux."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.1, thread_threshold=0.2))
    to_return.update(compare_to_n_days(test, threshold=0.1, thread_threshold=0.2))
    to_return.update(compare_to_tag(test, threshold=0.1, thread_threshold=0.2))
    return to_return

def sys_linux_standlone_c3_2xlarge(test):
    """Rules for a standalone setup on Linux on a c3.2xlarge AWS instance."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_n_days(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    return to_return

def sys_linux_standlone_c3_4xlarge(test):
    """Rules for a standalone setup on Linux on a c3.4xlarge AWS instance."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_n_days(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    return to_return

def longevity_linux_wt_shard(test):
    """Rules for a Linux WiredTiger shard."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.25, thread_threshold=0.25))
    # longevity tests are run once a week; 7-day check is not very useful
    to_return.update(compare_to_tag(test, threshold=0.25, thread_threshold=0.25))
    # max_lag check
    to_return.update(replica_lag_check(test, threshold=10))
    # possibly check on
    return to_return

def longevity_linux_wt_shard_csrs(test):
    """Rules for a Linux WiredTiger Config Server Replica Set shard ."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.25, thread_threshold=0.25))
    # longevity tests are run once a week; 7-day check is not very useful
    to_return.update(compare_to_tag(test, threshold=0.25, thread_threshold=0.25))
    # max_lag check
    to_return.update(replica_lag_check(test, threshold=10))
    # possibly check on
    return to_return

def longevity_linux_mmapv1_shard(test):
    """Rules for a Linux MMAPv1 shard."""

    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.25, thread_threshold=0.25))
    # longevity tests are run once a week; 7-day check is not very useful
    to_return.update(compare_to_tag(test, threshold=0.25, thread_threshold=0.25))
    # max_lag check
    to_return.update(replica_lag_check(test, threshold=10))
    # possibly check on
    return to_return


# project_id and variant uniquely identify the set of rules to check
# using a dictionary to help us choose the function with the right rules
CHECK_RULES = {
    'sys-perf': {
        'windows-1-node-replSet': sys_windows_1_node_repl_set,
        'windows-standalone': sys_windows_standalone,
        'linux-1-node-replSet': sys_linux_1_node_repl_set,
        'linux-standalone': sys_linux_standalone,
        'linux-3-shard': sys_linux_3_shard,
        'linux-3-node-replSet': sys_linux_3_node_repl_set,
        'linux-3-node-replSet-initialsync': sys_linux_3_node_repl_set_isync,
        'linux-oplog-compare': sys_linux_oplog_compare,
        'linux-standalone-c3-2xlarge': sys_linux_standlone_c3_2xlarge,
        'linux-standalone-c3-4xlarge': sys_linux_standlone_c3_4xlarge,
        },
    'mongo-longevity': {
        'linux-wt-shard': longevity_linux_wt_shard,
        'linux-wt-shard-csrs': longevity_linux_wt_shard_csrs,
        'linux-mmapv1-shard': longevity_linux_mmapv1_shard,
        }
    }



'''
Utility functions and classes - these are functions and classes that load and manipulates
test results for various checks
'''

def compare_one_throughput( # pylint: disable=too-many-arguments
        this_one, reference, label, thread_level="max", threshold=0.07, using_override=None):
    """
    Compare one data point from result series this_one to reference at thread_level
    if this_one is lower by threshold*reference return True.
    """

    (passed, log) = compare_one_result(this_one, reference, label,
                                       thread_level, default_threshold=threshold,
                                       using_override=using_override)
    print(log)
    return passed

def compare_throughputs( # pylint: disable=too-many-arguments
        this_one, reference, label, threshold=0.07, thread_threshold=0.1, using_override=None):
    ''' compare all points in result series this_one to reference

     Use different thresholds for max throughput, and per-thread comparisons
     return 'fail' if any of this_one is lower in any of the comparison
     otherwise return 'pass'
    '''

    if using_override is None:
        using_override = []
    failed = False

    # Don't do a comparison if the reference data is missing
    if not reference:
        return 'pass'

    # some tests may have higher noise margin and need different thresholds
    # this info is kept as part of the override file
    (threshold, thread_threshold, threshold_override) = read_threshold_overrides(
        this_one['name'], threshold, thread_threshold, overrides)

    if threshold_override:
        using_override.append("threshold")

    # Check max throughput first
    if compare_one_throughput(this_one, reference, label, "max", threshold, using_override):
        failed = True
    # Check for regression on threading levels
    thread_levels = [r for r in this_one["results"] if isinstance(this_one["results"][r], dict)]
    if len(thread_levels) > 1:
        for level in thread_levels:
            if compare_one_throughput(this_one, reference, label,
                                      level, thread_threshold, using_override):
                failed = True
    if not failed:
        return 'pass'
    return 'fail'

# pylint: disable=invalid-name
# pylint wants global variables to be written in uppercase, but changing all of the occurrences of
# the following ones would be too painful so we opt to locally disable the warning instead.
history = None
tag_history = None
overrides = None
regression_line = None
replica_lag_line = None
# pylint: enable=invalid-name

def main(args): # pylint: disable=too-many-locals,too-many-statements,too-many-branches
    """
    For each test in the result, we call the variant-specific functions to check for
    regressions and other conditions. We keep a count of failed tests in 'failed'.
    We also maintain a list of pass/fail conditions for all rules
    for every tests, which gets dumped into a report file at the end.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project_id", dest="project_id", help="project_id for the test in Evergreen")
    parser.add_argument("--task_name", dest="task_name", help="task_name for the test in Evergreen")
    parser.add_argument("-f", "--file", dest="hfile", help="path to json file containing"
                        "history data")
    parser.add_argument("-t", "--tagFile", dest="tfile", help="path to json file containing"
                        "tag data")
    parser.add_argument("--rev", dest="rev", help="revision to examine for regressions")
    parser.add_argument("--refTag", dest="reference", help=
                        "Reference tag to compare against. Should be a valid tag name")
    parser.add_argument(
        "--overrideFile", dest="ofile", help="File to read for comparison override information")
    parser.add_argument("--variant", dest="variant", help="Variant to lookup in the override file")
    parser.add_argument(
        "--report-file", help='File to write the report JSON file to. Defaults to "report.json".',
        default="report.json")
    parser.add_argument(
        "--out-file", help="File to write the results table to. Defaults to stdout.")
    parser.add_argument(
        "--reports-dir",
        help=(
            "The path to the reports directory created during the performance tests, which "
            "contains log files somewhere in its tree."))

    args = parser.parse_args(args)
    print(args.hfile)

    # Set up result histories from various files:
    # history - this series include the run to be checked, and previous or NDays
    # tag_history - this is the series that holds the tag build as comparison target
    # overrides - this series has the override data to avoid false alarm or fatigues
    # The result histories are stored in global variables within this module as they
    # are accessed across many rules.

    global history, tag_history, overrides, regression_line, replica_lag_line # pylint: disable=invalid-name,global-statement
    (history, tag_history, overrides) = read_histories(args.variant,
                                                       args.hfile, args.tfile, args.ofile)

    failed = 0
    results = []

    # regression summary table lines
    regression_line = []

    # replication lag table lines
    replica_lag_line = []

    # iterate through tests and check for regressions and other violations
    testnames = history.testnames()
    for test in testnames:
        result = {'test_file': test, 'exit_code': 0, 'log_raw': '\n'}
        to_test = {'ref_tag': args.reference}
        series = history.series_at_revision(test, args.rev)
        if series:
            to_test.update(series)
            result["start"] = series.get("start", 0)
            result["end"] = series.get("end", 1)
            if len(to_test) == 1:
                print("\tno data at this revision, skipping")
                continue
            # Use project_id and variant to identify the rule set
            # May want to use task_name for further differentiation
            try:
                # Redirect stdout to log_stdout to capture per test log
                real_stdout = sys.stdout
                log_stdout = StringIO.StringIO()
                sys.stdout = log_stdout
                result.update(CHECK_RULES[args.project_id][args.variant](to_test))
                # Store log_stdout in log_raw
                test_log = log_stdout.getvalue()
                result['log_raw'] += log_header(test)
                result['log_raw'] += test_log
                # Restore stdout (important) and print test_log to it
                sys.stdout = real_stdout

                if args.out_file is None:
                    print(result["log_raw"])
                else:
                    with open(args.out_file, "w") as out_file:
                        out_file.write(result["log_raw"])

            except Exception as err: # pylint: disable=broad-except
                # Need to restore and print stdout in case of Exception
                test_log = log_stdout.getvalue()
                sys.stdout = real_stdout
                print(test_log)
                print("The (project_id, variant) combination is not supported " \
                    "in post_run_check.py: {0}".format(str(err)))
                print(sys.exc_info()[0])
                sys.exit(1)
            if any(val == 'fail' for val in result.itervalues()):
                failed += 1
                result['status'] = 'fail'
            else:
                result['status'] = 'pass'
            results.append(result)

    report = {}
    report['failures'] = failed
    report['results'] = results

    # flush stdout to the log file
    sys.stdout.flush()

    # use the stderr to print replica_lag table
    if len(replica_lag_line) > 0:
        print("\n==============================", file=sys.stderr)
        print("Replication Lag Summary:", file=sys.stderr)
        printing_test = ""
        for line in replica_lag_line:
            if line[0] != printing_test:
                printing_test = line[0]
                print("\n%s" % printing_test, file=sys.stderr)
                print(
                    "%10s|%16s|%16s|%16s" % ("Thread", "Avg_lag", "Max_lag", "End_of_test_lag"),
                    file=sys.stderr)
                print("-"*10 + "+" + "-"*16 + "+" + "-"*16 + "+" + "-"*16, file=sys.stderr)
            print_line = '{0:>10}'.format(line[1])
            for data in line[2:]:
                formatted = '|{0:16.2f}'.format(data) if isinstance(data, float) else \
                    '|{0:>16}'.format(data)
                print_line = print_line + formatted
            print(print_line, file=sys.stderr)

    if args.reports_dir is not None:
        log_analysis_results, num_failures = log_analysis.analyze_logs(args.reports_dir)
        report['results'].extend(log_analysis_results)
        failed += num_failures

    # flush stderr to the log file
    sys.stderr.flush()

    with open(args.report_file, "w") as report_file:
        json.dump(report, report_file, indent=4, separators=(',', ': '))
    return 1 if failed > 0 else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
