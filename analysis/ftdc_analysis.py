"""
Functions for analyzing `FTDC` diagnostic data. Parse files to do some resource sanity checks.
"""

from __future__ import print_function
import inspect
import os
import logging

import datetime

import readers
import rules
import util

LOGGER = logging.getLogger(__name__)

RESOURCE_RULES_FTDC_FILE = {
    'sys-perf': {
        'default': [rules.ftdc_replica_lag_check],
        'linux-3-node-replSet-initialsync': []
    }
}

# rules run for every variant
COMMON_RULES = [rules.below_configured_cache_size,
                rules.compare_heap_cache_sizes,
                rules.below_configured_oplog_size]

RESOURCE_RULES_FTDC_CHUNK = {
    'sys-perf': {
        'default': COMMON_RULES + [rules.max_connections,  # rule not run for 3 shard
                                   rules.repl_member_state],  # rule not run for initialsync
        'linux-3-shard': COMMON_RULES + [rules.repl_member_state],
        'linux-3-node-replSet-initiasync': COMMON_RULES + [rules.max_connections]
    }
}

# Functions to format the failure messages

def ftdc_date_parse(time_in_s):
    """Helper to convert timestamps in s to human-readable format. Matches formatting in the
    timeseries web tool

    :type time_in_s: int
    :rtype: str
    """
    time_offset = rules.INITIAL_TIME + datetime.timedelta(seconds=time_in_s)
    return time_offset.strftime('%Y-%m-%d %H:%M:%SZ')

def failure_message(rule_info, task_run_time):
    """Standardize the way that we return a failure message.

    :param dict rule_info: every resource rule, upon failure, must return a dictionary in
    accordance with the key-value mapping specified in the failure_collection function defined
    below.
      Exception: If a single resource rule handles checks over multiple members, the dictionary
      will contain the attribute 'members' with a list[dict], where each dict follows the standard
      format.
    :param int task_run_time: how long did the task itself run? Assess relative duration of failure
    """
    failure_msg = ''
    if 'members' in rule_info and rule_info['members']:
        if 'additional' in rule_info:
            for key, value in rule_info['additional'].iteritems():
                failure_msg += '\t| {0}: {1}'.format(key, value)
        for _, member_info in rule_info['members'].iteritems():
            failure_msg += failure_message(member_info, task_run_time)
        return failure_msg

    first_failure_time = ftdc_date_parse(rule_info['times'][0]/rules.MS)
    failure_msg += '\n  First failure occurred at time {0}'.format(first_failure_time)

    first_failure_values = rule_info['compared_values'][0]
    for index in xrange(len(first_failure_values)):
        failure_msg += '\n\t{0}: {1}'.format(
            rule_info['labels'][index], first_failure_values[index])

    if 'additional' in rule_info:
        for key, value in rule_info['additional'].iteritems():
            failure_msg += '\n\t{0}: {1}'.format(key, value)

    duration_failure = len(rule_info['times'])
    if float(duration_failure)/task_run_time > 0.10:  # proportion of time in failing state
        failure_msg += '\nFailure detected {0}s out of the {1}s it took to run this task'.format(
            duration_failure, task_run_time)
    else:
        times = [ftdc_date_parse(ts/rules.MS) for ts in rule_info['times']]
        failure_msg += '\n\tFailures seen at times: {0}'.format(str(times))

    return failure_msg

def unify_chunk_failures(chunk_failure_info):
    """Failures are collected for each FTDC chunk. Though this may be an unnecessary step to take
    for our current resource rule output (reporting 1st occurrence of failure), if we ever want to
    return 'smarter' failure messages, we might want to go through all the timestamps and values
    compared in a rule. Rather than divide failures by chunk, this function collects the results
    into a single dictionary for each resource rule.

    :param dict chunk_failure_info: a dictionary of resource rules mapped to a list of
       the failures that occurred in different FTDC chunks.
       (key: resource rule) -> (value: list of failure info dicts)
    :rtype: dict (key: resource rule) -> (value: single failure info dict)
    """
    all_failure_instances = {}
    for rule_name, failure_info_list in chunk_failure_info.iteritems():
        if 'members' in failure_info_list[0]:
            add_to = failure_info_list[0]['members']
            for index in xrange(1, len(failure_info_list)):
                current = failure_info_list[index]['members']
                all_members = set(current.keys()) | set(add_to.keys())
                for member in all_members:
                    if member not in add_to:
                        add_to[member] = {}
                        add_to[member]['times'] = current[member]['times']
                        add_to[member]['compared_values'] = current[member]['compared_values']
                    elif member in current:
                        add_to[member]['times'] += current[member]['times']
                        add_to[member]['compared_values'] += current[member]['compared_values']
            all_failure_instances[rule_name] = {'members': add_to}
        else:
            add_to = failure_info_list[0]
            for index in xrange(1, len(failure_info_list)):
                current = failure_info_list[index]
                add_to['times'] += current['times']
                add_to['compared_values'] += current['compared_values']
            all_failure_instances[rule_name] = add_to
    return all_failure_instances

def resource_rules(dir_path, project, variant, constant_values=None, perf_file_path=None):
    """Implemented for variants in sys-perf: given the FTDC metrics for a variant's task, check the
    resource rules available to the variant.

    :param str dir_path: path to the directory we recursively search for FTDC diagnostic data files
    :param str project: Evergreen project ID
    :param str variant: build variant to check
    :param dict constant_values: some rules take in constants to compare current values against
    :param str perf_file_path: set `perf_file_path` to the path of the performance results file
    (probably `perf.json`) generated by the test runner, which contains relevant timestamp data.
    """
    result = {
        'end': 1, 'start': 0
    }
    if not constant_values:
        constant_values = {}
    constant_values['test_times'] = None
    if perf_file_path:
        LOGGER.info('Getting test times from `%s`', perf_file_path)
        try:
            constant_values['test_times'] = util.get_test_times(perf_file_path)
        except IOError:
            LOGGER.error('Failed to read file `%s`', perf_file_path)
    ftdc_files_dict = _get_ftdc_file_paths(dir_path)
    if not ftdc_files_dict:
        result['status'] = 'pass'
        result['log_raw'] = '\nNo FTDC metrics files found. Skipping resource sanity checks.'
    else:
        # depending on variant, there can be multiple hosts and therefore multiple FTDC data files
        full_log_raw = ''
        for host_alias, full_path in ftdc_files_dict.iteritems():
            LOGGER.info('Reading FTDC file `%s`', full_path)
            (passed_checks, log_raw) = _process_ftdc_file(full_path,
                                                          project,
                                                          variant,
                                                          constant_values)
            if not passed_checks:
                full_log_raw += ('Failed resource sanity checks for host {0}').format(
                    host_alias)
                full_log_raw += log_raw
        if full_log_raw:
            result['status'] = 'fail'
            result['exit_code'] = 1
        else:
            result['status'] = 'pass'
            result['exit_code'] = 0
            full_log_raw = '\nPassed resource sanity checks.'
        result['log_raw'] = full_log_raw
    result['test_file'] = 'resource_sanity_checks'
    return result

def _process_ftdc_file(path_to_ftdc_file, project, variant, constant_values):  # pylint: disable=too-many-locals
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

    try: #pylint: disable=too-many-nested-blocks
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
            for chunk_rule in util.get_project_variant_rules(
                    project, variant, RESOURCE_RULES_FTDC_CHUNK):
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

    # reader.py throws a general exception
    except Exception: #pylint: disable=broad-except
        LOGGER.warning("Caught exception when trying to read FTDC data for path=%s",
                       path_to_ftdc_file)
        return(False, '\nFailed to read FTDC data for {0}'.format(path_to_ftdc_file))

    # check rules that require data from the whole FTDC run (rather than by chunk)
    file_rule_failures = _ftdc_file_rule_evaluation(
        path_to_ftdc_file, project, variant, constant_values['test_times'])

    if not failures_per_chunk and not file_rule_failures:
        return (True, '\nPassed resource sanity checks.')
    else:
        log_raw = _ftdc_log_raw(file_rule_failures,
                                unify_chunk_failures(failures_per_chunk),
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
        log_raw += failure_message(rule_failure_info, task_run_time)
    if file_rule_failures:
        log_raw += _ftdc_file_failure_raw(file_rule_failures, task_run_time)
    log_raw += '\n'
    print(log_raw)
    return log_raw

def _ftdc_file_rule_evaluation(path_to_ftdc_file, project, variant, test_times):
    """Some rules require data from the entire FTDC run.

    :type path_to_ftdc_file: str
    :type project: str
    :type variant: str
    :rtype: dict
    """
    file_rules = util.get_project_variant_rules(project, variant, RESOURCE_RULES_FTDC_FILE)
    file_rule_failures = {}
    for resource_rule in file_rules:
        check_failed = resource_rule(path_to_ftdc_file, test_times)
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
            lag_failure_message = failure_message(failure, task_run_time)
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
            # in the short term, there are also diag-p*-*-* directories with
            # diagnostic data.
            # The previous line and the following check skips analysis
            # for the diag-p* directories (this check can probably be removed later)
            if host_identification:
                ftdc_files = os.listdir(os.path.join(dir_path, find_directory))
                files = [fi for fi in ftdc_files if not fi.endswith(".interim")]
                if len(files) != 1:
                    LOGGER.info('%s FTDC metrics files in %s. Skipping.',
                                len(files), parent_directory_name)
                else:
                    full_path = os.path.join(dir_path, find_directory, files[0])
                    ftdc_metrics_paths[host_identification] = full_path
    return ftdc_metrics_paths

def _get_host_ip_info(diagnostic_dir_name):
    """Directory names follow the naming convention: <CATEGORY>-<INDEX> where INDEX is
    between 0 and (# of instances of that category) and CATEGORY is one of
    'mongod', 'mongos', 'configsvr', or 'workload_client'. In this instance
    only 'mongod' or 'configsvr' could be valid.

    :param str diagnostic_dir_name: directory name, parent directory enclosing the
               diagnostic.data directory containing FTDC files
    :rtype: str the diagnostic directory name if no '-' otherwise it is legacy and
    None is returned for the moment.
    """
    if '-' in diagnostic_dir_name:
        return None
    else:
        return diagnostic_dir_name
