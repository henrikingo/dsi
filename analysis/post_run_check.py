#!/usr/bin/env python2.7
"""
Example usage:
post_run_check.py -f history_file.json --rev 18808cd923789a34abd7f13d62e7a73fafd5ce5f
        --project_id $pr_id --variant $variant --reports-dir ..
Loads the history json file, and looks for regressions at the revision 18808cd...
Evergreen project_id and variant are used to uniquely identify the rule set to use.
Additionally, runs resource sanity checks and detects anomalous messages in the mongod.log.
Will exit with status code 1 if any regression is found or resource checks failed, 0 otherwise.
"""

from __future__ import print_function
import argparse
import inspect
import json
import logging
import os
import StringIO
import sys
import warnings

from datetime import timedelta
from dateutil import parser as date_parser

import readers
import rules
from util import read_histories, compare_one_result, log_header, read_threshold_overrides
import log_analysis
import arg_parsing

logging.basicConfig(level=logging.INFO)

def project_test_rules(project, variant, test):
    """For each test, run the specified regression rules listed in PROJECT_TEST_RULES and return
    a dictionary with rules as keys and pass/fail information as values.

    :type project: str
    :type variant: str
    :type test: dict
    :rtype: dict
    """
    to_return = {}
    regression_rules = _get_project_variant_rules(project, variant, PROJECT_TEST_RULES)
    threshold_values = _get_project_variant_rules(project, variant, rules.THRESHOLDS)

    for regression_rule_function in regression_rules:
        build_args = {'test': test}
        arguments_needed = inspect.getargspec(regression_rule_function).args
        for parameter in arguments_needed:
            if parameter in threshold_values:
                build_args[parameter] = threshold_values[parameter]
            elif parameter in rules.PROJECT_TEST_CONSTANTS:
                build_args[parameter] = rules.PROJECT_TEST_CONSTANTS[parameter]
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
    else:
        return {'PreviousCompare': compare_throughputs(
            test, previous, 'Previous', threshold, thread_threshold)}

def compare_to_n_days(test, threshold, thread_threshold, ndays=7):
    """check if there is a regression in the last week"""

    daysprevious = history.series_at_n_days_before(test['name'], test['revision'], ndays)
    if not daysprevious:
        print('        no reference data for test {} with NDays'.format(test['name']))
        return {}
    using_override = []
    if test['name'] in overrides['ndays']:
        try:
            override_time = date_parser.parse(overrides['ndays'][test['name']]['create_time'])
            this_time = date_parser.parse(test['create_time'])
            if (override_time < this_time) and ((override_time + timedelta(days=ndays))
                                                >= this_time):
                daysprevious = overrides['ndays'][test['name']]
                using_override.append('reference')
            else:
                print('Out of date override found for ndays. Not using')
        except KeyError as err:
            err_msg = ('Key error accessing overrides for ndays. '
                       'Key {0} does not exist for test {1}').format(str(err), test['name'])
            print(err_msg, file=sys.stderr)

    return {'NDayCompare': compare_throughputs(test, daysprevious,
                                               'NDays', threshold,
                                               thread_threshold,
                                               using_override)}

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
        return {'BaselineCompare': compare_throughputs(test,
                                                       reference,
                                                       'Baseline',
                                                       threshold,
                                                       thread_threshold,
                                                       using_override)}
    else:
        return {}

# Failure & other condition checks

def replica_lag_check(test, lag_threshold=10):
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
            avg_lag = 'NA'
        if 'replica_max_lag' in test['results'][level]:
            max_lag = test['results'][level]['replica_max_lag']
            lag_entry += 1
        else:
            max_lag = 'NA'
        if 'replica_end_of_test_lag' in test['results'][level]:
            end_of_test_lag = test['results'][level]['replica_end_of_test_lag']
            lag_entry += 1
        else:
            end_of_test_lag = 'NA'
        total_lag_entry += 1
        # mark the test failed if max_lag is higher than threshold
        if max_lag != 'NA':
            if float(max_lag) > lag_threshold:
                status = 'fail'
                print('   ---> replica_max_lag (%s) > threshold(%s) seconds at %s' %
                      (max_lag, lag_threshold, level))
        # print an entry in the replica_lag summary table, regardless of pass/fail
        if lag_entry > 0:
            replica_lag_line.append((test['name'], level, avg_lag, max_lag, end_of_test_lag))

    if total_lag_entry == 0:
        # no lag information
        return {}
    if status == 'pass':
        print('        replica_lag under threshold ({}) seconds'.format(lag_threshold))
    return {'Replica_lag_check': status}

# FTDC resource check

def resource_rules(dir_path, project, variant, constant_values=None):
    """Implemented for variants in sys-perf: given the FTDC metrics for a variant's task, check the
    resource rules available to the variant.

    :param str dir_path: path to the directory we recursively search for FTDC diagnostic data files
    :param str project: Evergreen project ID
    :param str variant: build variant to check
    :param dict constant_values: some rules take in constants to compare current values against
    """
    result = {
        'end': 1, 'exit_code': 0, 'start': 0
    }
    if not constant_values:
        constant_values = {}
    ftdc_files_dict = _get_ftdc_file_paths(dir_path)
    if not ftdc_files_dict:
        result['status'] = 'pass'
        result['log_raw'] = '\nNo FTDC metrics files found. Skipping resource sanity checks.'
    else:
        # depending on variant, there can be multiple hosts and therefore multiple FTDC data files
        full_log_raw = ''
        for (host_name, public_ip), full_path in ftdc_files_dict.iteritems():
            print('Reading {0}'.format(full_path))
            (passed_checks, log_raw) = _process_ftdc_file(full_path,
                                                          project,
                                                          variant,
                                                          constant_values)
            if not passed_checks:
                full_log_raw += ('Failed resource sanity checks for host {0} ({1})').format(
                    host_name, public_ip)
                full_log_raw += log_raw
        if full_log_raw:
            result['status'] = 'fail'
        else:
            result['status'] = 'pass'
            full_log_raw = '\nPassed resource sanity checks.'
        result['log_raw'] = full_log_raw
    result['test_file'] = 'resource_sanity_checks'
    return result

def _process_ftdc_file(path_to_ftdc_file, project, variant, constant_values):
    """Iterates through chunks in a single FTDC metrics file and checks the resource rules

    :param str path_to_ftdc_file: path to a FTDC metrics file
    :param str project: Evergreen project ID
    :param str variant: build variant to check
    :param dict constant_values: some rules take in constants to compare current values against
    :rtype: tuple(bool, str)
            bool: whether the checks passed/failed for a host
            str: raw log information
    """
    failures_per_chunk = {}
    task_run_time = 0

    for chunk in readers.read_ftdc(path_to_ftdc_file):
        # a couple of asserts to make sure the chunk is not malformed
        assert all(len(chunk.values()[0]) == len(v) for v in chunk.values()), \
            ('Metrics from file {0} do not all have same number of collected '
             'samples in the chunk').format(os.path.basename(path_to_ftdc_file))
        assert len(chunk.values()[0]) != 0, \
            ('No data captured in chunk from file {0}').format(
                os.path.basename(path_to_ftdc_file))
        assert rules.FTDC_KEYS['time'] in chunk, \
            ('No time information in chunk from file {0}').format(
                os.path.basename(path_to_ftdc_file))

        # proceed with rule-checking.
        times = chunk[rules.FTDC_KEYS['time']]
        task_run_time += len(times)
        for chunk_rule in _get_project_variant_rules(project, variant, RESOURCE_RULES_FTDC_CHUNK):
            build_args = {'chunk': chunk, 'times': times}
            arguments_needed = inspect.getargspec(chunk_rule).args

            # gather any missing arguments
            (build_args, constant_values) = _fetch_constant_arguments(chunk,
                                                                      arguments_needed,
                                                                      build_args,
                                                                      constant_values)
            if len(build_args) < len(arguments_needed):
                continue  # could not find all the necessary metrics in this chunk
            else:
                output = chunk_rule(**build_args)
                if output:
                    rule_name = chunk_rule.__name__
                    if rule_name not in failures_per_chunk:
                        failures_per_chunk[rule_name] = []
                    failures_per_chunk[rule_name].append(output)

    # check rules that require data from the whole FTDC run (rather than by chunk)
    file_rule_failures = _ftdc_file_rule_evaluation(path_to_ftdc_file, project, variant)

    if not failures_per_chunk and not file_rule_failures:
        return (True, '\nPassed resource sanity checks.')
    else:
        log_raw = _ftdc_log_raw(file_rule_failures,
                                rules.unify_chunk_failures(failures_per_chunk),
                                task_run_time)
        return (False, log_raw)

def _fetch_constant_arguments(chunk, arguments_needed, arguments_present, constant_values):
    """Helper to update arguments_present and constant_values. Uses mapping in rules.FETCH_CONSTANTS
    to retrieve needed values from the FTDC metrics. These configured values, such as oplog maxSize,
    are known to be stored in the FTDC data and so do not need to be manually passed in.

    :param collections.OrderedDict chunk:
    :param list[str] arguments_needed: from inspecting the function
    :param dict arguments_present: the arguments & values that we currently have
    :param dict constant_values: the constants we currently have
    :rtype: tuple(dict, dict) updated dictionaries for arguments_present and constant_values
    """
    for parameter in arguments_needed:
        if parameter not in arguments_present:
            if parameter not in constant_values:
                found_constant = rules.FETCH_CONSTANTS[parameter](chunk)
                if found_constant:
                    constant_values[parameter] = found_constant
                    arguments_present[parameter] = found_constant
            else:
                arguments_present[parameter] = constant_values[parameter]
    return (arguments_present, constant_values)

def _ftdc_log_raw(file_rule_failures, chunk_rule_failures, task_run_time):
    """Produce the raw log output for failures from a single FTDC file

    :param dict file_rule_failures: failure info gathered from checks run on the whole FTDC file
    :param dict chunk_rule_failures: failure info gathered from checks run per-chunk
    :param int task_run_time: how long did this task run?
    :rtype: str
    """
    log_raw = ''
    for rule_name, rule_failure_info in chunk_rule_failures.iteritems():
        log_raw += '\nRULE {0}'.format(rule_name)
        log_raw += rules.failure_message(rule_failure_info, task_run_time)
    if file_rule_failures:
        log_raw += _ftdc_file_failure_raw(file_rule_failures, task_run_time)
    log_raw += '\n'
    print(log_raw)
    return log_raw

def _ftdc_file_rule_evaluation(path_to_ftdc_file, project, variant):
    """Some rules require data from the entire FTDC run.

    :type path_to_ftdc_file: str
    :type project: str
    :type variant: str
    :rtype: dict
    """
    file_rules = _get_project_variant_rules(project, variant, RESOURCE_RULES_FTDC_FILE)
    file_rule_failures = {}
    for resource_rule in file_rules:
        check_failed = resource_rule(path_to_ftdc_file)
        if check_failed:
            file_rule_failures[resource_rule.__name__] = check_failed
    return file_rule_failures

def _ftdc_file_failure_raw(failures_dict, task_run_time):
    """Helper to output log raw message for rules checked across the whole FTDC file, rather than
    by chunk. This only really applies to replica lag failure collection right now. Potentially
    useful if resource rule checks grow more complex in the future.

    :param dict failures_dict: key: rule name, value: failure info. currently a list because the
           repl lag rule gathers new failure information for each change in primary member.
    :param int task_run_time: how long in seconds did the task run?
    :rtype: str
    """
    log_raw = ''
    for rule_name, failures_list in failures_dict.iteritems():
        log_raw = '\nRULE {0}'.format(rule_name)
        for failure in failures_list:
            lag_failure_message = rules.failure_message(failure, task_run_time)
            log_raw += lag_failure_message
    return log_raw

# Functions for fetching FTDC diagnostic data. Used to facilitate resource sanity checks during
# a sys-perf task. We might consider moving resource check functions
# into a separate module similar to the way we import mongod.log parsing functions (PERF-329)

def _get_ftdc_file_paths(dir_path):
    """Recursively search `dir_path` for diagnostic.data directories and return a list of fully
    qualified FTDC metrics file paths.

    :type dir_path: str
    :rtype: dict with key: (host name, ip address) tuple and value: full path to FTDC metrics file
    """
    find_directory = 'diagnostic.data'
    ftdc_metrics_paths = {}
    for dir_path, sub_folder, _ in os.walk(dir_path):
        if find_directory in sub_folder:
            parent_directory_name = os.path.basename(dir_path)
            host_identification = _get_host_ip_info(parent_directory_name)
            ftdc_files = os.listdir(os.path.join(dir_path, find_directory))
            files = [fi for fi in ftdc_files if not fi.endswith(".interim")]
            if len(files) != 1:
                warnings.warn('{0} FTDC metrics files in {1}. Skipping.'.format(
                    len(files), parent_directory_name))
            else:
                full_path = os.path.join(dir_path, find_directory, files[0])
                ftdc_metrics_paths[host_identification] = full_path
    return ftdc_metrics_paths

def _get_host_ip_info(diagnostic_dir_name):
    """Directory names follow the naming convention: diag-p<INDEX>-<PUBLIC_IP> where INDEX is
    between 1 and (# of mongod instances). Could also use reports/ips.py if the variables there
    were imported.

    :param str diagnostic_dir_name: dash-separated directory name, parent directory enclosing the
               diagnostic.data directory containing FTDC files
    :rtype: tuple(str, str) host name and public IP address
    """
    naming_convention = diagnostic_dir_name.split('-')
    return (naming_convention[1], naming_convention[2])

# Utility functions and classes - these are functions and classes that load and manipulate
# test results for various checks

def compare_one_throughput( # pylint: disable=too-many-arguments
        this_one, reference, label, thread_level='max', threshold=0.07, using_override=None):
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
            if compare_one_throughput(this_one, reference, label,
                                      level, thread_threshold, using_override):
                failed = True
    if not failed:
        return 'pass'
    return 'fail'

def _get_project_variant_rules(project, variant, rules_dict):
    """The rules we want to check are specified in nested dictionaries. They all follow the same
       structure, so this is a short helper to fetch a list of functions, corresponding to the
       rules evaluated for a given project and variant.

    :type project: str
    :type variant: str
    :type rules_dict: dict
    :rtype: list[functions]
    """
    if project not in rules_dict:
        return []
    project_rules = rules_dict[project]
    if variant not in project_rules:
        return project_rules['default']
    else:
        return project_rules[variant]

# pylint: disable=invalid-name
# pylint wants global variables to be written in uppercase, but changing all of the occurrences of
# the following ones would be too painful so we opt to locally disable the warning instead.
history = None
tag_history = None
overrides = None
regression_line = None
replica_lag_line = None
# pylint: enable=invalid-name

# These rules are run for every test.
# TODO: it is best practice to declare all constants at the top of a Python file. This can be done
# when we move the regression rules to rules.py. This will likely happen pending the refactoring
# we do during the PERF-580 perf_regression_check and post_run_check merge; right now they remain
# in post_run_check because they currently access some number of global variables.

REGRESSION_RULES = [compare_to_previous, compare_to_n_days, compare_to_tag]
REGRESSION_AND_REPL_LAG_RULES = REGRESSION_RULES + [replica_lag_check]

PROJECT_TEST_RULES = {
    'sys-perf': {
        'default': REGRESSION_RULES,
        'linux-3-shard': REGRESSION_AND_REPL_LAG_RULES,
        'linux-3-node-replSet': REGRESSION_AND_REPL_LAG_RULES,
        'linux-3-node-replSet-initialsync': REGRESSION_AND_REPL_LAG_RULES
    },
    'mongo-longevity': {
        'default': [compare_to_previous, compare_to_tag, replica_lag_check]
    }
}

RESOURCE_RULES_FTDC_FILE = {
    'sys-perf': {
        # TODO: commenting out until this rule has been revised some more.
        # 'default': [rules.ftdc_replica_lag_check],
        'default': [],
        'linux-3-node-replSet-initialsync': []
    }
}

RESOURCE_RULES_FTDC_CHUNK = {
    'sys-perf': {
        'default': [rules.below_configured_cache_size, rules.compare_heap_cache_sizes,
                    rules.max_connections, rules.below_configured_oplog_size],
        'linux-3-shard': [rules.below_configured_cache_size, rules.compare_heap_cache_sizes,
                          rules.below_configured_oplog_size]
    }
}

def main(args): # pylint: disable=too-many-locals,too-many-statements,too-many-branches
    """
    For each test in the result, we call the variant-specific functions to check for
    regressions and other conditions. We keep a count of failed tests in 'failed'.
    We also maintain a list of pass/fail conditions for all rules
    for every tests, which gets dumped into a report file at the end.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--project_id', dest='project_id', help='project_id for the test in Evergreen')
    parser.add_argument('--task_name', dest='task_name', help='task_name for the test in Evergreen')
    parser.add_argument('-f', '--file', dest='hfile', help='path to json file containing '
                        'history data')
    parser.add_argument('-t', '--tagFile', dest='tfile', help='path to json file containing '
                        'tag data')
    parser.add_argument('--rev', dest='rev', help='revision to examine for regressions')
    parser.add_argument('--refTag', dest='reference', help=
                        'Reference tag to compare against. Should be a valid tag name')
    parser.add_argument(
        '--overrideFile', dest='ofile', help='File to read for comparison override information')
    parser.add_argument('--variant', dest='variant', help='Variant to lookup in the override file')
    parser.add_argument(
        "--report-file", help='File to write the report JSON file to. Defaults to "report.json".',
        default="report.json")
    parser.add_argument(
        "--out-file", help="File to write the results table to. Defaults to stdout.")
    arg_parsing.add_args(parser, "log analysis")
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
    task_max_thread_level = 0
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
                result.update(project_test_rules(args.project_id, args.variant, to_test))
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

            except Exception as err: # pylint: disable=broad-except
                # Need to restore and print stdout in case of Exception
                test_log = log_stdout.getvalue()
                sys.stdout = real_stdout
                print(test_log)
                print('The (project_id, variant) combination is not supported ' \
                    'in post_run_check.py: {0}'.format(str(err)))
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
        print('\n==============================', file=sys.stderr)
        print('Replication Lag Summary:', file=sys.stderr)
        printing_test = ''
        for line in replica_lag_line:
            if line[0] != printing_test:
                printing_test = line[0]
                print('\n%s' % printing_test, file=sys.stderr)
                print(
                    '%10s|%16s|%16s|%16s' % ('Thread', 'Avg_lag', 'Max_lag', 'End_of_test_lag'),
                    file=sys.stderr)
                print('-'*10 + '+' + '-'*16 + '+' + '-'*16 + '+' + '-'*16, file=sys.stderr)
            print_line = '{0:>10}'.format(line[1])
            for data in line[2:]:
                formatted = '|{0:16.2f}'.format(data) if isinstance(data, float) else \
                    '|{0:>16}'.format(data)
                print_line = print_line + formatted
            print(print_line, file=sys.stderr)

    if args.log_analysis is not None:
        log_analysis_results, _ = log_analysis.analyze_logs(args.log_analysis, args.perf_file)
        report['results'].extend(log_analysis_results)
        # are there resource rules to check for this project?
        if (args.project_id in RESOURCE_RULES_FTDC_FILE
                and args.project_id in RESOURCE_RULES_FTDC_CHUNK):
            # The only reason this is declared here presently is because I get the maximum thread
            # level from a task during the test regression rule checks. Maximum thread level is
            # passed in to the '# of connections' rule we are currently using.
            resource_constant_values = {
                'max_thread_level': task_max_thread_level
            }
            resource_rule_outcome = resource_rules(
                args.log_analysis, args.project_id, args.variant, resource_constant_values)
            report['results'] += [resource_rule_outcome]

    else:
        print('Did not specify a value for parameter --log-analysis. Skipping mongod.log and '
              'FTDC resource sanity checks.')


    # flush stderr to the log file
    sys.stderr.flush()

    with open(args.report_file, 'w') as report_file:
        json.dump(report, report_file, indent=4, separators=(',', ': '))
    return 1 if failed > 0 else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
