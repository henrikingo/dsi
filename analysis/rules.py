"""Module of constants and rules used in our resource sanity checks. Used in post_run_check.py.
"""

import datetime
import re
from dateutil import parser as date_parser

import readers

# TODO: currently lots of globals in here. PERF-580 (unify post_run_check and perf_regression_check)
# will likely involve refactoring to address this global constants vs. config file issue.
# Discussion with the team during PERF-193 has given me a good idea of what our options are.

FTDC_KEYS = {
    'cache_size': ('serverStatus', 'wiredTiger', 'cache', 'bytes currently in the cache'),
    'heap_size': ('serverStatus', 'tcmalloc', 'generic', 'heap_size'),
    'oplog_size': ('local.oplog.rs.stats', 'size'),
    'curr_connections': ('serverStatus', 'connections', 'current'),
    'max_cache_size': ('serverStatus', 'wiredTiger', 'cache', 'maximum bytes configured'),
    'max_oplog_size': ('local.oplog.rs.stats', 'maxSize'),
    'time': ('start',),
    'repl_set_status': ('replSetGetStatus', 'members', '([0-9])+')
}

# Constants used during rule checks.

INITIAL_TIME = date_parser.parse('1970-01-01T00:00:00Z')  # for formatting log failure messages

FLAG_MEMBER_STATES = {3: 'RECOVERING', 6: 'UNKNOWN', 8: 'DOWN', 9: 'ROLLBACK', 10: 'REMOVED'}
STARTUP_MEMBER_STATES = {0: 'STARTUP', 5: 'STARTUP2'}

# cache size must be below (1 + CACHE_ALLOCATOR_OVERHEAD) * heap size.
CACHE_ALLOCATOR_OVERHEAD = .08

# current oplog size must be below (1 + WT_OPLOG_BUFFER)
WT_OPLOG_BUFFER = .10

# in seconds, when is the member lag too large?
MS = 1000.0
REPL_MEMBER_LAG_THRESHOLD_S = 10.0
REPL_MEMBER_LAG_THRESHOLD_MS = REPL_MEMBER_LAG_THRESHOLD_S * MS

CONSTANTS = {
    'sys-perf': {
        'default': {
            'threshold': 0.08,
            'thread_threshold': 0.12,
            'lag_threshold': REPL_MEMBER_LAG_THRESHOLD_S,
            'ndays': 7.0
        },
        'linux-oplog-compare': {
            'threshold': 0.1,
            'thread_threshold': 0.2
        },
        'linux-3-node-replSet-initialsync': {
            # from Judah: initial sync uses 16 threads to put data into the database
            'max_thread_level': 16.0
        }
    },
    'mongo-longevity': {
        'default': {
            'threshold': 0.25,
            'thread_threshold': 0.25
        }
    }
}

def _fetch_constant(chunk, key):
    if key in chunk:
        return chunk[key][0]
    else:
        return None

# Some constants can be fetched from the FTDC data. Find the first occurrence of these metrics in
# the FTDC chunks and use them accordingly.
def get_configured_cache_size(chunk):
    """Helper function to fetch maximum cache size value from a chunk

    :param collection.OrderedDict chunk: FTDC JSON chunk
    :rtype: int|None if chunk does not contain the needed key.
    """
    return _fetch_constant(chunk, FTDC_KEYS['max_cache_size'])

def get_configured_oplog_size(chunk):
    """Helper function to fetch maximum oplog size value from a chunk

    :param collection.OrderedDict chunk: FTDC JSON chunk
    :rtype: int|None if chunk does not contain the needed key.
    """
    return _fetch_constant(chunk, FTDC_KEYS['max_oplog_size'])

def get_repl_members(chunk):
    """Helper function to fetch a list of members with available repl set status information.

    :param collection.OrderedDict chunk: FTDC JSON chunk
    :rtype: list[str]
    """
    match_on_member_key = ';'.join(FTDC_KEYS['repl_set_status'])
    members = set()
    for key in chunk:
        re_key = ';'.join(key)
        match = re.match(match_on_member_key, re_key)
        if match:
            member = match.group(1)
            members.add(member)
    member_list = list(sorted(members))
    return member_list

# Map each of the helper functions to the parameter their return values will correspond to in the
# resource rules.
# Note: Still thinking about the best way to approach this mapping. The dictionary, considered a
# constant, should be located above all functions in this file. However, the helper functions
# in FETCH_CONSTANTS need to be declared before they are stored. Calls into question whether this
# was the right design choice or not.
FETCH_CONSTANTS = {
    'configured_cache_size': get_configured_cache_size,
    'configured_oplog_size': get_configured_oplog_size,
    'repl_member_list': get_repl_members
}

# Functions related to failure output formatting

def ftdc_date_parse(time_in_s):
    """Helper to convert timestamps in s to human-readable format. Matches formatting in the
    timeseries web tool

    :type time_in_s: int
    :rtype: str
    """
    time_offset = INITIAL_TIME + datetime.timedelta(seconds=time_in_s)
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

    first_failure_time = ftdc_date_parse(rule_info['times'][0]/MS)
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
        times = [ftdc_date_parse(ts/MS) for ts in rule_info['times']]
        failure_msg += '\n\tFailures seen at times: {0}'.format(str(times))

    return failure_msg

def failure_collection(failure_times, compared_values, labels, other_rule_info=None):
    """Helper function to standardize the dictionary data structure that stores failure information.
    TODO: Each rule currently needs to initialize variables to collect the following parameters.
          Currently, this means any modification to the structure requires code updates in
          every rule function. I've thought about designing a general "rule framework" function
          where you pass in a custom comparison function, but wanted to hold off in case
          there were other suggestions for improving this design.

    :param list[int] failure_times: times (in ms) where failures occurred.
    :param list[tuple(*int)] compared_values: values that failed the resource check
    :param tuple labels: values in each tuple need to have labels to generate informative failure
                         messages
    :param dict other_rule_info: a dict containing any additional information we need to include
                                 in a failure message.
    :rtype: dict
    """
    if not failure_times:
        return {}
    rule_info = {}
    rule_info['times'] = failure_times
    rule_info['compared_values'] = compared_values
    rule_info['labels'] = labels
    if other_rule_info:
        rule_info['additional'] = other_rule_info
    return rule_info

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

# Resource sanity check rules

def below_configured_cache_size(chunk, times, configured_cache_size):
    """Is the current cache size below (1+CACHE_ALLOCATOR_OVERHEAD) * WT configured cache size?

    :param collection.OrderedDict chunk: FTDC JSON chunk
    :param list[int] times: the time at which each metric value was collected
    :param int configured_cache_size: specified cache size configuration in bytes
    :rtype: dict
    """
    if FTDC_KEYS['cache_size'] not in chunk:
        return {}

    cache_size_values = chunk[FTDC_KEYS['cache_size']]

    failure_times = []
    labels = ('current cache size (bytes)',)
    compared_values = []
    additional = {'WT configured cache size (bytes)': configured_cache_size}

    for index, cache_size in enumerate(cache_size_values):
        if cache_size > (1 + CACHE_ALLOCATOR_OVERHEAD) * configured_cache_size:
            failure_times.append(times[index])
            compared_values.append((cache_size,))
    return failure_collection(failure_times, compared_values, labels, additional)

def compare_heap_cache_sizes(chunk, times):
    """Is the current cache size within (1+CACHE_ALLOCATOR_OVERHEAD) * tcmalloc generic heap size?

    :param collection.OrderedDict chunk: FTDC JSON chunk
    :param list[int] times: the time at which each metric value was collected
    :rtype: dict
    """
    if FTDC_KEYS['cache_size'] not in chunk or FTDC_KEYS['heap_size'] not in chunk:
        return {}

    cache_size_values = chunk[FTDC_KEYS['cache_size']]
    heap_size_values = chunk[FTDC_KEYS['heap_size']]

    failure_times = []
    labels = ('current cache size (bytes)', 'tcmalloc generic heap size (bytes)')
    compared_values = []

    for index, cache_size in enumerate(cache_size_values):
        heap_size = heap_size_values[index]
        if cache_size >= (1 + CACHE_ALLOCATOR_OVERHEAD) * heap_size:
            failure_times.append(times[index])
            compared_values.append((cache_size, heap_size))
    return failure_collection(failure_times, compared_values, labels)

def max_connections(chunk, times, max_thread_level, repl_member_list):
    """Does the total number of connections remain below some expected limit?
    NOTES:
      - This rule is NOT applied to the sharded variant. From discussion, it is difficult to
        upper bound the # of connections on a sharded cluster.
      - In the future, we should think about how to account for mixed workloads, specific tests,
        and how the expected # of connections differs for primaries vs. secondaries

    :param collection.OrderedDict chunk: FTDC JSON chunk
    :param list[int] times: the time at which each metric value was collected
    :param int max_thread_level: the maximum thread level that is specified in the whole task
    :param list[str]: for replSets, the upper bound depends on the number of members
    :rtype: dict
    """
    if FTDC_KEYS['curr_connections'] not in chunk:
        return {}
    curr_connection_values = chunk[FTDC_KEYS['curr_connections']]

    if not repl_member_list:  # standalone
        upper_bound_factor = 0
    else:
        upper_bound_factor = 2 * len(repl_member_list)

    failure_times = []
    labels = ('number of current connections',)
    compared_values = []
    additional = {
        'max thread level for this task': max_thread_level,
        'connections between members? (2 * N)': upper_bound_factor,
        'connections to MC and shell': 2,
        'rule': '# connections <= (2 * max thread level + 2 + {0})'.format(upper_bound_factor)
    }
    for index, num_connections in enumerate(curr_connection_values):
        if num_connections > (max_thread_level * 2) + 2 + upper_bound_factor:
            failure_times.append(times[index])
            compared_values.append((num_connections,))
    return failure_collection(failure_times, compared_values, labels, additional)

def below_configured_oplog_size(chunk, times, configured_oplog_size):
    """Is the current oplog size below (1 + WT_OPLOG_BUFFER) * configured oplog max size?

    :param collection.OrderedDict chunk: FTDC JSON chunk
    :param list[int] times: the time at which each metric value was collected
    :param int configured_oplog_size: specified oplog size configuration in MB
    :rtype: dict
    """
    if FTDC_KEYS['oplog_size'] not in chunk:
        return {}
    oplog_size_values = chunk[FTDC_KEYS['oplog_size']]
    upper_bound_factor = (1 + WT_OPLOG_BUFFER)

    failure_times = []
    labels = ('current oplog size (MB)',)
    compared_values = []
    additional = {
        'WT configured max oplog size (MB)': configured_oplog_size,
        'rule': 'current size <= (max size * {0})'.format(upper_bound_factor)
    }

    for index, oplog_size in enumerate(oplog_size_values):
        if oplog_size > configured_oplog_size * upper_bound_factor:
            failure_times.append(times[index])
            compared_values.append((oplog_size,))
    return failure_collection(failure_times, compared_values, labels, additional)

# NOTE: NONE OF THESE RULES ARE BEING CHECKED AS OF 7/18/2016. See line 490 in post_run_check.py
# for the list of active resource sanity checks.

def repl_member_state(chunk, times, repl_member_list):
    """Do any of the members ever go into a "bad" state? (i.e. RECOVERING; see FLAG_MEMBER_STATES.)

    :param collection.OrderedDict chunk: FTDC JSON chunk
    :param list[int] times: the time at which each metric value was collected
    :param list[str] repl_member_list: list of replica set members in this variant
    :rtype: dict
    """
    member_states = {}
    for member in repl_member_list:
        member_state_key = ('replSetGetStatus', 'members', member, 'state')
        if member_state_key not in chunk:
            continue
        member_state_values = chunk[member_state_key]

        failure_times = []
        labels = ('member ' + member + ' state',)
        compared_values = []
        for index, state in enumerate(member_state_values):
            if state in FLAG_MEMBER_STATES:
                failure_times.append(times[index])
                compared_values.append((FLAG_MEMBER_STATES[state],))
        failure = failure_collection(failure_times, compared_values, labels)
        if failure:
            member_states[member] = failure
    if member_states:
        return {'members': member_states}
    else:
        return {}

def find_primary(chunk, repl_member_list):
    """Is there a member in state PRIMARY right now?

    :param collection.OrderedDict chunk: FTDC JSON chunk
    :param list[str] repl_member_list: list of replica set members in this variant
    :rtype: str|None
    """
    for member in repl_member_list:
        member_state_key = ('replSetGetStatus', 'members', member, 'state')
        if member_state_key not in chunk:
            return None
        member_state = set(chunk[member_state_key])
        if len(member_state) != 1:
            # No formal error logging here right now.
            print 'State transition occurred mid-chunk. Member {0} states: {1}'.format(
                member, str(member_state))
            continue
        if member_state.pop() == 1:
            return member
    return None

def ftdc_replica_lag_check(path_to_ftdc_file):
    """Replica set lag computation requires some knowledge of the lag times over entire chunks,
    so the standard structure of our resource checks (in the rules module) will not apply.

    :param str path_to_file: path to a FTDC metrics file
    :rtype: list[dict] each dict corresponds to failure info for a different primary member.
            (accounts for possible election in the middle of a task)
    """
    repl_member_list = []
    collect_by_primary = []  # in case election occurs, lag info is specific to each primary

    lag_info_dict = {'times': []}
    current_primary = None

    for chunk in readers.read_ftdc(path_to_ftdc_file):
        if not repl_member_list:  # need a list of members in the replica set
            repl_member_list = get_repl_members(chunk)  # is there member info in this chunk?
            if not repl_member_list:
                continue

        primary = find_primary(chunk, repl_member_list)
        if not primary:  # skip if no primary
            continue

        # a primary member has been identified. check the newly fetched primary against our
        # currently declared primary
        if not current_primary:
            current_primary = primary
        elif primary is not current_primary:
            # an election has occurred. in this case, we store the information gathered thus far
            # using our currently declared primary and reset the necessary variables as we move
            # forward with the newly named primary
            collect_by_primary.append(lag_info_dict)
            lag_info_dict = {'times': []}
            current_primary = primary

        primary_optimedate_key = ('replSetGetStatus', 'members', current_primary, 'optimeDate')
        if primary_optimedate_key not in chunk:  # skip if no optimeDate data for primary
            continue

        secondary_members = repl_member_list
        secondary_members.remove(current_primary)
        # add the members as keys to the lag info dict if we are collecting lag info for the first
        # time with this primary.
        for member in secondary_members:
            if member not in lag_info_dict:
                lag_info_dict[member] = []

        collect_lag = _chunk_member_lag(chunk, secondary_members, chunk[primary_optimedate_key])
        # the two lengths may not be equivalent if, for whatever reason, optimeDate data for some
        # member is missing for this chunk. shouldn't happen, but if it does, we want to ignore
        # the data from this chunk.
        if len(collect_lag.keys()) == len(secondary_members):
            # `times` is an array of timestamps corresponding to when each sample was collected.
            # note that each chunk contains samples collected over some duration.
            times = chunk[FTDC_KEYS['time']]
            lag_info_dict['primary'] = current_primary
            lag_info_dict['times'] += times
            for member, member_lag in collect_lag.iteritems():
                lag_info_dict[member] += member_lag

    # after processing the whole file, append the remaining lag info dictionary
    collect_by_primary.append(lag_info_dict)

    return _lag_failures_per_primary(collect_by_primary, repl_member_list)

def _chunk_member_lag(chunk, repl_member_list, primary_optimedates):
    """Helper function to compute secondary lag from values in a chunk

    :param collection.OrderedDict chunk: FTDC JSON chunk
    :param list[str] repl_member_list: list of all members in the replSet
    :param str primary: which member is the primary?
    :param list[int] primary_optimedates: optimeDate values for the primary
    :rtype: dict (lag values for the secondaries)
    """
    collect_chunk_lag = {}
    for member in repl_member_list:
        member_optimedate_key = ('replSetGetStatus', 'members', member, 'optimeDate')
        if member_optimedate_key not in chunk:
            break
        else:
            member_optimedate_values = chunk[member_optimedate_key]
            member_lag = []
            for index, secondary_optimedate in enumerate(member_optimedate_values):
                lag = primary_optimedates[index] - secondary_optimedate
                member_lag.append(lag)
            collect_chunk_lag[member] = member_lag
    return collect_chunk_lag

def _lag_failures_per_primary(lag_info_per_primary, repl_member_list):
    """Helper function to flag issues with repl secondary lag. Wrapper around the
    _flag_unacceptable_lag function call because lag information is collected `per primary`

    :param list[dict] lag_info_per_primary: list of lag information dicts specific to each newly
           elected primary
    :param list[str] repl_member_list: list of all members in the replSet
    :rtype: list[dict] each dict corresponds to failure info for a different primary member
    """
    failures = []
    for lag_info_dict in lag_info_per_primary:
        if lag_info_dict['times']:  # check that lag information was indeed collected...
            flagged = _flag_unacceptable_lag(lag_info_dict, repl_member_list)
            if flagged:
                failures.append(flagged)
    return failures

def _flag_unacceptable_lag(lag_info_dict, repl_member_list):  # pylint: disable=too-many-branches
    """Helper function to analyze lag times and flag potential problems

    :param dict lag_info_dict: contains lag information for all members, the primary, and the
           timestamps for all the data collected.
    :param list[str] repl_member_list: list of all members in the replSet
    :rtype: dict (failure information)
    """
    failure_by_member = {}
    num_samples = len(lag_info_dict['times'])
    if num_samples <= 1:  # if lag is too large at beginning, it could just be a false positive.
        return {}
    for member in repl_member_list:
        if lag_info_dict['primary'] is member:
            continue

        failure_times = []
        compared_values = []

        member_lag = lag_info_dict[member]
        previous = {'lag': lag_info_dict['times'][0], 'time': member_lag[0]}

        # again, it's possible that we start off with a false positive
        if previous['lag'] > REPL_MEMBER_LAG_THRESHOLD_MS:
            last_false_positive = {'lag': previous['lag'], 'time': previous['time']}
        else:
            last_false_positive = None

        for index in xrange(1, num_samples):
            current_time = lag_info_dict['times'][index]
            current_lag = member_lag[index]
            if last_false_positive and current_lag < last_false_positive['lag']:
                last_false_positive = None

            # current lag appears greater than our specified threshold
            if current_lag > REPL_MEMBER_LAG_THRESHOLD_MS:
                # lag can't grow greater than 1s per s
                if (current_lag - previous['lag']) > (current_time - previous['time']):
                    last_false_positive = {'lag': current_lag, 'time': current_time}
                elif last_false_positive:
                    time_from_fp = current_time - last_false_positive['time']
                    # accounting for the FP value detection, lag has still grown unacceptably large
                    if current_lag > last_false_positive['lag'] + time_from_fp:
                        failure_times.append(current_time)
                        compared_values.append((current_lag,))
                else:
                    failure_times.append(current_time)
                    compared_values.append((current_lag/MS,))
            previous['time'] = current_time
            previous['lag'] = current_lag
        failure = failure_collection(failure_times,
                                     compared_values,
                                     ('member {0} lag (s)'.format(member),))
        if failure:
            failure_by_member[member] = failure
    if failure_by_member:
        return {'members': failure_by_member,
                'additional': {'using lag threshold (s)': REPL_MEMBER_LAG_THRESHOLD_S,
                               'primary member': lag_info_dict['primary']}
               }
    else:
        return {}
