#!/usr/bin/env python2.7
"""
Example usage:
post_run_check.py -f history_file.json --rev 18808cd923789a34abd7f13d62e7a73fafd5ce5f
        --project_id $pr_id --variant $variant --reports-analysis reports
Loads the history json file, and looks for regressions at the revision 18808cd...
Evergreen project_id and variant are used to uniquely identify the rule set to use.
Additionally, runs resource sanity checks and detects anomalous messages in the mongod.log.
Will exit with status code 1 if any regression is found or resource checks failed, 0 otherwise.
"""

from __future__ import print_function
import argparse
import fnmatch
import inspect
import json
import logging
import StringIO
import sys
import traceback

from datetime import timedelta
import re

import os
from dateutil import parser as date_parser

import rules
from exit_status import read_exit_status, EXIT_STATUS_OK
from util import read_histories, compare_one_result, log_header, \
                 read_threshold_overrides, get_project_variant_rules
import ftdc_analysis
import log_analysis
import ycsb_throughput_analysis
import arg_parsing

logging.basicConfig(level=logging.INFO)


def unique_post_check_name(filename, omit='reports'):
    """ convert filename to a unique exit status check name. Just using the file name would
    result in multiple ambiguous checks called 'test_output.log'. This extra processing is
    required to generate some more meaningful names.

    For example, 'reports/benchRun/test_output.log'
    will be converted to 'benchRun test_output.log'

    :param str filename: the full path of the file.
    :param str omit: remove this if it is the first part of the path (defaults to reports).

    :return: str a more human readable test check name.
    """
    parts = os.path.normpath(filename).split(os.path.sep)
    if parts[0] == omit:
        parts = parts[1:]
    return " ".join(parts)


# TODO: PERF-1299 should be implemented in the following function
def check_test_output_files(reports_dir_path, pattern='test_output.log'):
    """
    This function scans the reports subdirectories for files that match the *pattern* (defaults to
    'test_output.log'). These log files contain the stdout and stderr streams for the test
    processes.

    In certain cases, these files contain the test output (e.g. benchRun). But in other cases, the
    actual test results are elsewhere (e.g. fio / iperf where the results are in json files).

    Currently we only analyze the test output log files for the exit status (which is encoded on
    the last line of the file).

    The line must be the last in the file and of the format:
        exit_status: [0-9] .*

    If there is no matching line, then this is an unknown error.

    The following output is generated for 'reports/ycsb_50read50update/test_output.log':
    Failing result:
    {
                "status": "fail",
                "test_file": 'reports/ycsb_50read50update/test_output.log',
                "log_raw": 'message',
                "start": 0,
                "exit_code": 1
    }

    passing result:
    {
                "status": "pass",
                "test_file": 'reports/ycsb_50read50update/test_output.log',
                "start": 0,
                "exit_code": 0
    }


    :param str reports_dir_path: the report directory.
    :param str pattern: the output filename pattern.
    :returns: array of checks of the format shown above (empty if no error).
    """
    test_output_log_files = []
    for root, _, filenames in os.walk(reports_dir_path):
        for filename in fnmatch.filter(filenames, pattern):
            test_output_log_files.append(os.path.join(root, filename))

    results = []
    for test_output_log_file in test_output_log_files:
        exit_status = read_exit_status(test_output_log_file)

        result = {
            "status": "pass" if exit_status.status == EXIT_STATUS_OK else "fail",
            "test_file": unique_post_check_name(test_output_log_file),
            "start": 0,
            "exit_code": exit_status.status,
            "log_raw": str(exit_status)
        }
        results.append(result)
    return results


def check_core_file_exists(reports_dir_path, pattern="core.*"):
    """Analyze all the file in the directory tree rooted at `reports_dir_path`,
    and return a list of test-result dictionaries ready to be placed in the report JSON generated
    by `post_run_check`/`perf_regression_check`.

    The check first looks for directories matching the following patterns  'mongo?.[0-9]' or '
    configsvr.[0-9]'

    If no directories match then an empty array is returned (this case covers a system failure or
    the case where nothing is captured for some other reason).

    For each matching directory, it will return a result with the 'test_name' field set to
    'core.<directory>'.

    *Note*: 'test_name' is the name of the check, not the name of an actual file. Unlike the other
    sanity checks, in the majority of cases there won't a file.
    *Note*: directory will be something like mongod.0, mongod.1, mongos.2, configsvr.3.

    In each matching directories, files matching the pattern parameter are checked (default to
    'core.*').

    If one or more core file is found per directory then a record is created with:
      * 'test_file' set to 'core.<directory>'. As described above, this is the name of the sanity
         check.
      * 'status' set to 'fail'.
      * 'exit_code' set to 1.
      * 'log_raw'  set to 'No core files found' or a comma separated list of the base filenames
         (i.e. excluding the parent directory). These are the messages displayed within
         the test results widget in the dashboard.

    A Failing check result looks like:
    {
                "status": "fail",
                "test_file": 'core.<directory>',
                "log_raw": '<comma separated core files>',
                "start": 0,
                "exit_code": 1
    }

    If no core is found then each directory generates a result like the following:
    {
                "status": "pass",
                "test_file": 'core.<directory>',
                "log_raw": 'No core files found',
                "start": 0,
                "exit_code": 0
    }
    """
    # List of directories that could contain a core file
    mongo_dir_paths = []

    # Core files, if they happen, are downloaded into reports/test_id/mongod.0/core.*
    for test_name in os.listdir(reports_dir_path):
        test_dir_path = os.path.join(reports_dir_path, test_name)
        if os.path.isdir(test_dir_path):
            for mongo_name in os.listdir(test_dir_path):
                mongo_dir_path = os.path.join(test_dir_path, mongo_name)
                if (os.path.isdir(mongo_dir_path) and fnmatch.fnmatch(mongo_name, 'mongo?.[0-9]')
                        or fnmatch.fnmatch(mongo_name, 'configsvr.[0-9]')):
                    mongo_dir_paths.append(mongo_dir_path)

    def _format_msg_body(basenames=None):
        msg_body = "\nNo core files found" if not basenames else \
            "\ncore files found: {}\nNames: \n{}".format(
                len(basenames), ", ".join(basenames))
        return msg_body

    results = []
    if mongo_dir_paths:
        cores_lookup = {}
        for mongo_dir_path in mongo_dir_paths:
            cores_lookup[mongo_dir_path] = []

            for potential_corefile in os.listdir(mongo_dir_path):
                if fnmatch.fnmatch(potential_corefile, pattern):
                    cores_lookup[mongo_dir_path].append(potential_corefile)

        for mongo_dir_path in sorted(cores_lookup.iterkeys()):
            cores = [core for core in cores_lookup[mongo_dir_path]]
            mongo_host = os.path.basename(mongo_dir_path)
            test_id = os.path.basename(os.path.dirname(mongo_dir_path))
            results.append({
                "status": "fail" if cores else "pass",
                "test_file": 'core.{}.{}'.format(test_id, mongo_host),
                "log_raw": _format_msg_body(cores),
                "start": 0,
                "exit_code": 1 if cores else 0
            })
    return results


def project_test_rules(project, variant, is_patch, test):
    """For each test, run the specified regression rules listed in PROJECT_TEST_RULES and return
    a dictionary with rules as keys and pass/fail information as values.

    :type project: str
    :type variant: str
    :type test: dict
    :rtype: dict
    """
    to_return = {}
    regression_rules = get_project_variant_rules(project, variant, PROJECT_TEST_RULES)

    for regression_rule_function in regression_rules:
        if is_patch:
            if regression_rule_function.__name__ == "compare_n_days_delayed_trigger":
                continue
        build_args = {'test': test}
        arguments_needed = inspect.getargspec(regression_rule_function).args
        for parameter in arguments_needed:
            constant_found = _lookup_constant_value(project, variant, parameter)
            if constant_found:
                build_args[parameter] = constant_found
        result = regression_rule_function(**build_args)
        to_return.update(result)

    return to_return


# Regression rules


def compare_to_previous(test, threshold, thread_threshold):
    """Compare against the performance data from the previous run."""

    previous = history.series_at_n_before(test['name'], test['revision'], 1)
    if not previous:
        print('        no previous data, skipping')
        return {'PreviousCompare': 'pass'}
    return {
        'PreviousCompare':
            compare_throughputs(test, previous, 'Previous', threshold, thread_threshold)
    }


def compare_n_days_delayed_trigger(test, threshold, thread_threshold, ndays=7):
    """NDays case with delayed trigger"""
    test_name = test['name']
    test_revision = test['revision']
    previous = history.series_at_n_before(test_name, test_revision, 1)
    target = history.series_at_n_days_before(test_name, test_revision, ndays)
    if not target:
        print('        no reference data for test {} with NDays'.format(test_name))
        return {}
    using_override = []
    if test_name in overrides['ndays']:
        try:
            override_time = date_parser.parse(overrides['ndays'][test_name]['create_time'])
            this_time = date_parser.parse(test['create_time'])
            override_before_create_time = override_time < this_time
            override_ndays_after_create = (override_time + timedelta(days=ndays)) >= this_time
            if override_before_create_time and override_ndays_after_create:
                target = overrides['ndays'][test_name]
                using_override.append('ndays')
            else:
                print('Out of date override found for ndays. Not using.')
        except KeyError as err:
            err_msg = ('Key error accessing overrides for ndays. '
                       'Key {0} does not exist for test {1}').format(str(err), test_name)
            print(err_msg, file=sys.stderr)
    return _delayed_trigger_analysis(test, target, previous, 'NDays', threshold, thread_threshold,
                                     using_override)


def compare_tag_delayed_trigger(test, threshold, thread_threshold):
    """Baseline case with delayed trigger"""
    if tag_history:
        test_name = test['name']
        previous = history.series_at_n_before(test_name, test['revision'], 1)
        target = tag_history.series_at_tag(test_name, test['ref_tag'])
        if not target:
            print('        no reference data for test {0} with baseline'.format(test_name))
            return {}
        using_override = []
        if test_name in overrides['reference']:
            using_override.append('reference')
            target = overrides['reference'][test_name]
        return _delayed_trigger_analysis(test, target, previous, 'Baseline', threshold,
                                         thread_threshold, using_override)
    else:
        return {}


def _delayed_trigger_analysis(  # pylint: disable=too-many-arguments
        test, target, previous, label, threshold, thread_threshold, using_override):
    """Implement a delayed trigger based on the previous commit to reduce false alarms"""
    previous_status = 'fail'
    if previous is not None:
        previous_status = compare_throughputs(previous, target, 'silent', threshold,
                                              thread_threshold, using_override)

    check_name = label + 'Compare'
    if previous_status == 'fail':
        return {
            check_name:
                compare_throughputs(test, target, label, threshold, thread_threshold,
                                    using_override)
        }
    else:
        # because of the 'silent' label, the log raw output isn't updated by this
        must_fail = compare_throughputs(test, target, 'silent', threshold * 1.5,
                                        thread_threshold * 1.5, using_override)
        # only log the results for comparison to the standard threshold and thread_threshold.
        this_status = compare_throughputs(test, target, label, threshold, thread_threshold,
                                          using_override)
        if must_fail == 'fail':
            print('  {} check failed because of drop greater than 1.5 x threshold'.format(label))
            return {check_name: 'fail'}
        if this_status == 'fail':
            print('  {} check considered passed as this is the first drop'.format(label))
        return {check_name: 'pass'}


def compare_to_tag(test, threshold, thread_threshold):
    """Compare against the tagged performance data in `tag_history`."""

    # if tag_history is undefined, skip this check completely
    if tag_history:
        reference = tag_history.series_at_tag(test['name'], test['ref_tag'])
        if not reference:
            print('        no reference data for test {} with baseline'.format(test['name']))
            return {}
        using_override = []
        if test['name'] in overrides['reference']:
            using_override.append('reference')
            reference = overrides['reference'][test['name']]
        return {
            'BaselineCompare':
                compare_throughputs(test, reference, 'Baseline', threshold, thread_threshold,
                                    using_override)
        }
    else:
        return {}


# Utility functions and classes - these are functions and classes that load and manipulate
# test results for various checks


def compare_one_throughput(  # pylint: disable=too-many-arguments
        this_one,
        reference,
        label,
        thread_level='max',
        threshold=0.07,
        using_override=None):
    """
    Compare one data point from result series this_one to reference at thread_level
    if this_one is lower by threshold*reference return True.
    """
    (passed, log) = compare_one_result(
        this_one,
        reference,
        label,
        thread_level,
        default_threshold=threshold,
        using_override=using_override)
    if label != 'silent':
        print(log)
    return passed


def compare_throughputs(  # pylint: disable=too-many-arguments
        this_one,
        reference,
        label,
        threshold=0.07,
        thread_threshold=0.1,
        using_override=None):
    """compare all points in result series this_one to reference

     Use different thresholds for max throughput, and per-thread comparisons
     return 'fail' if any of this_one is lower in any of the comparison
     otherwise return 'pass'
    """
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
        using_override.append('threshold')

    # Check max throughput first
    if compare_one_throughput(this_one, reference, label, 'max', threshold, using_override):
        failed = True
    # Check for regression on threading levels
    thread_levels = [r for r in this_one['results'] if isinstance(this_one['results'][r], dict)]
    if len(thread_levels) > 1:
        for level in thread_levels:
            if compare_one_throughput(this_one, reference, label, level, thread_threshold,
                                      using_override):
                failed = True
    if not failed:
        return 'pass'
    return 'fail'


def _lookup_constant_value(project, variant, constant_name):
    """Looks in the rules.CONSTANTS dictionary for default or variant-specific constant values

    :type project: str
    :type variant: str
    :type constant_name: str
    :rtype: float|None
    """
    if project not in rules.CONSTANTS:
        return None
    project_constants = rules.CONSTANTS[project]
    if variant in project_constants and constant_name in project_constants[variant]:
        return project_constants[variant][constant_name]
    elif constant_name in project_constants['default']:
        return project_constants['default'][constant_name]
    return None


# pylint: disable=invalid-name
# pylint wants global variables to be written in uppercase, but changing all of the occurrences of
# the following ones would be too painful so we opt to locally disable the warning instead.
history = None
tag_history = None
overrides = None
replica_lag_line = None
# pylint: enable=invalid-name

# As discussed, new rules are subject to a quarantine period irrespective of project/variant/etc.
# The report.json `test_file` regex value of these checks are listed here; will not increment the
# number of failures in the report for tests specified in this variable.
QUARANTINED_RULES = [
    r'mongod\.log\.([0-9])+', r'resource_sanity_checks', r'ycsb-throughput-analysis',
    r'db-hash-check', r'validate-indexes-and-collections'
]

# These rules are run for every test.
# TODO: it is best practice to declare all constants at the top of a Python file. This can be done
# when we move the regression rules to rules.py. This will likely happen pending the refactoring
# we do during the PERF-580 perf_regression_check and post_run_check merge; right now they remain
# in post_run_check because they currently access some number of global variables.

REGRESSION_RULES = [compare_to_previous, compare_n_days_delayed_trigger, compare_to_tag]

PROJECT_TEST_RULES = {
    'sys-perf': {
        'default': REGRESSION_RULES,
        'linux-3-shard': REGRESSION_RULES,
        'linux-3-node-replSet': REGRESSION_RULES,
        'linux-3-node-replSet-initialsync': REGRESSION_RULES
    },
    'mongo-longevity': {
        'default': [compare_to_previous, compare_to_tag]
    }
}


def main(args):  # pylint: disable=too-many-locals,too-many-statements,too-many-branches
    """
    For each test in the result, we call the variant-specific functions to check for
    regressions and other conditions. We keep a count of failed tests in 'failed'.
    We also maintain a list of pass/fail conditions for all rules
    for every tests, which gets dumped into a report file at the end.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--project_id', dest='project_id', help='project_id for the test in Evergreen')
    parser.add_argument('--task_name', dest='task_name', help='Deprecated. See --task.')
    parser.add_argument(
        '-f', '--file', dest='hfile', help='path to json file containing '
        'history data')
    parser.add_argument(
        '-t', '--tagFile', dest='tfile', help='path to json file containing '
        'tag data')
    parser.add_argument('--rev', dest='rev', help='revision to examine for regressions')
    parser.add_argument(
        '--refTag',
        dest='reference',
        help='Reference tag to compare against. Should be a valid tag name')
    parser.add_argument(
        '--overrideFile', dest='ofile', help='File to read for comparison override information')
    parser.add_argument('--variant', dest='variant', help='Variant to lookup in the override file')
    parser.add_argument('--task', dest='task', help='Evergreen task name for the test')
    parser.add_argument(
        "--report-file",
        help='File to write the report JSON file to. Defaults to "report.json".',
        default="report.json")
    parser.add_argument(
        "--out-file", help="File to write the results table to. Defaults to stdout.")
    parser.add_argument(
        "--ycsb-throughput-analysis",
        help=("Analyze the throughput-over-time data from YCSB log files. The argument to this "
              "flag should be the directory to recursively search for the files."))
    # TODO: PERF-675 to remove this. Present for backwards compatibility right now.
    parser.add_argument(
        "--is-patch",
        action='store_true',
        default=False,
        dest='is_patch',
        help='If true, will skip NDays comparison (see PERF-386).')
    parser.add_argument(
        "--log-analysis",
        help=("This argument is only present for backwards compatibility. To be removed."))

    arg_parsing.add_args(parser, "reports analysis")
    args = parser.parse_args(args)
    if args.task_name and not args.task:
        args.task = args.task_name

    # Set up result histories from various files:
    # history - this series include the run to be checked, and previous or NDays
    # tag_history - this is the series that holds the tag build as comparison target
    # overrides - this series has the override data to avoid false alarm or fatigues
    # The result histories are stored in global variables within this module as they
    # are accessed across many rules.
    global history, tag_history, overrides, replica_lag_line  # pylint: disable=invalid-name,global-statement
    (history, tag_history, overrides) = read_histories(args.variant, args.task, ofile=args.ofile)
    task_max_thread_level = 0
    results = []

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
            result['start'] = series.get('start', 0)
            result['end'] = series.get('end', 1)
            if len(to_test) == 1:
                print('\tno data at this revision, skipping')
                continue
            # Use project_id and variant to identify the rule set
            # May want to use task_name for further differentiation
            try:
                # Redirect stdout to log_stdout to capture per test log
                real_stdout = sys.stdout
                log_stdout = StringIO.StringIO()
                sys.stdout = log_stdout
                result.update(
                    project_test_rules(args.project_id, args.variant, args.is_patch, to_test))
                # Store log_stdout in log_raw
                test_log = log_stdout.getvalue()
                result['log_raw'] += log_header(test)
                result['log_raw'] += test_log
                # Restore stdout (important) and print test_log to it
                sys.stdout = real_stdout

                # what is the maximum thread level for this test?
                test_max_thread_level = max(int(x) for x in to_test['results'].keys())
                # update the maximum thread level of the entire task as necessary
                task_max_thread_level = max(test_max_thread_level, task_max_thread_level)

                if args.out_file is None:
                    print(result['log_raw'])
                else:
                    with open(args.out_file, 'w') as out_file:
                        out_file.write(result['log_raw'])

            except Exception as err:  # pylint: disable=broad-except
                # Need to restore and print stdout in case of Exception
                test_log = log_stdout.getvalue()
                sys.stdout = real_stdout
                print(test_log)
                print('The (project_id, variant) combination is not supported ' \
                    'in post_run_check.py: {0}'.format(str(err)))
                print(sys.exc_info()[0])
                print(sys.exc_info()[1])
                traceback.print_tb(sys.exc_info()[2])
                sys.exit(1)
            if any(val == 'fail' for val in result.itervalues()):
                result['status'] = 'fail'
            else:
                result['status'] = 'pass'
            results.append(result)

    report = {}
    report['results'] = results

    # flush stdout to the log file
    sys.stdout.flush()

    if args.reports_analysis is not None:
        results = check_test_output_files(args.reports_analysis)
        report['results'].extend(results)

        results = check_core_file_exists(args.reports_analysis)
        report['results'].extend(results)

        log_analysis_results, _ = log_analysis.analyze_logs(args.reports_analysis, args.perf_file)
        report['results'].extend(log_analysis_results)
        # are there resource rules to check for this project?
        if (args.project_id in ftdc_analysis.RESOURCE_RULES_FTDC_FILE
                and args.project_id in ftdc_analysis.RESOURCE_RULES_FTDC_CHUNK):
            # Maximum thread level is passed in to the '# of connections' rule
            # we are currently using.
            max_thread_level = _lookup_constant_value(args.project_id, args.variant,
                                                      'max_thread_level')
            if not max_thread_level:
                max_thread_level = task_max_thread_level
            resource_constant_values = {'max_thread_level': max_thread_level}
            resource_rule_outcome = ftdc_analysis.resource_rules(
                args.reports_analysis, args.project_id, args.variant, resource_constant_values,
                args.perf_file)
            report['results'] += [resource_rule_outcome]

        db_correctness_results = rules.db_correctness_analysis(args.reports_analysis)
        report['results'].extend(db_correctness_results)
    else:
        print('Did not specify a value for parameter --reports-analysis. Skipping mongod.log and '
              'FTDC resource sanity checks.')

    if args.ycsb_throughput_analysis is not None:
        analysis_results = ycsb_throughput_analysis.analyze_ycsb_throughput(
            args.ycsb_throughput_analysis)
        report['results'].extend(analysis_results)

    num_failures = 0
    for test_result in report['results']:
        match_on_rule = any(
            re.match(rule_regex, test_result['test_file']) for rule_regex in QUARANTINED_RULES)
        if test_result['status'] == 'fail' and not match_on_rule:
            num_failures += 1
    report['failures'] = num_failures

    # flush stderr to the log file
    sys.stderr.flush()

    with open(args.report_file, 'w') as report_file:
        json.dump(report, report_file, indent=4, separators=(',', ': '))
    return 1 if num_failures > 0 else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
