#!/usr/bin/env python2.7
'''
Iterate through tests to evaluate their states to display in the performance
dashboard against the specified baselines. Output is written to dashboard.json
which in turn is sent to the Evergreen database.

Example usage:
 dashboard_gen.py -f history_file.json --rev
        18808cd923789a34abd7f13d62e7a73fafd5ce5f --project_id $pr_id --variant
        $variant --jira-user user --jira-password passwd
'''
from __future__ import print_function

import argparse
import json
import sys
import requests

from util import read_histories, get_override, compare_one_result_base


# tests are classified into one of the following states
# When combining states from multiple checks, the highest valued state wins
TEST_STATE = {
    'pass': 1,
    'forced accept': 2,
    'undesired': 3,
    'unacceptable': 4,
    'no data': 5
}

# project_id and variant uniquely identify the set of rules to check
# using a dictionary to help us choose the function with the right rules
# defaults are defined at both project and global level; if a project/variant
# combination cannot be found, move up one level for default values
THRESHOLDS = {
    'sys-perf': {
        'linux-oplog-compare': {
            'undesired': 0.25, 'thread_undesired': 0.38,
            'unacceptable': 0.38, 'thread_unacceptable': 0.57
            }
        },
    'performance': {
        'default': {
            'undesired': 0.1, 'thread_undesired': 0.15,
            'unacceptable': 0.15, 'thread_unacceptable': 0.23
            }
        },
    'mongo-longevity': {
        'linux-wt-shard': {
            'undesired': 0.25, 'thread_undesired': 0.25,
            'unacceptable': 0.40, 'thread_unacceptable': 0.40
            },
        'linux-mmapv1-shard': {
            'undesired': 0.25, 'thread_undesired': 0.25,
            'unacceptable': 0.40, 'thread_unacceptable': 0.40
            }
        },
    'default': {
        'undesired': 0.1, 'thread_undesired': 0.15,
        'unacceptable': 0.15, 'thread_unacceptable': 0.23
        }
    }
# if only one threshold is defined, such as in the case of
# using a treshold_override, we use that for undesired and use
# a multiplier to define the unacceptable
THRESHOLD_MULTIPLIER = 1.5
# Fudge factors used for sample noise in multi-trial tests
NOISE_MULTIPLE = 1
THREAD_NOISE_MULTIPLE = 2

# default repl lag threshold check to 15 seconds
REPL_LAG_THRESHOLD = 15

# test data series
HISTORY = None
TAG_HISTORY = None
OVERRIDE_INFO = None

'''
Checks section -
    All checks return a dictionary that contains information used by
    the dashboard. The information include state, notes, ticket
    and perf_ratio. A check may return only a subset of the information
    that is relevant to the conditions it checks.
'''

def throughput_check(test, ref_tag, project_id, variant, jira_user, jira_password):
    ''' compute throughput ratios for all points in result series this_one
     over reference. Classify a test into a result['state'] based on the ratios.
     Use different thresholds for max throughput, and per-thread comparisons. '''
    # pylint: disable=too-many-locals,too-many-arguments,too-many-branches,too-many-statements

    # start the state as 'pass', if any override is used move it to 'forced accept'
    # after comparison to reference, move it to unacceptable or undesired if needed
    check_result = {'state': 'pass', 'notes': '', 'ticket': [],
                    'perf_ratio': 1}

    # if TAG_HISTORY is undefined, skip this check completely
    if TAG_HISTORY:
        reference = TAG_HISTORY.series_at_tag(test['name'], ref_tag)
        # Don't do a comparison if the reference data is missing
        if not reference:
            check_result['notes'] += "No reference data for test in baseline\n"
            return check_result
        # throughput override and ticket handling
        override = get_override(test['name'], 'reference', OVERRIDE_INFO)
        if override:
            (use_override_for_reference, ticket_list) = \
                check_ticket_state(override['ticket'], jira_user, jira_password)
            check_result['ticket'].extend(ticket_list)
            if use_override_for_reference:
                check_result['state'] = 'forced accept'
                check_result['notes'] += 'Override used for baseline throughput.'
                reference = override

    # get the thresholds to use using project/variant
    # if combination is not found, use project defaults
    # if project default is undefined, use global defaults
    try:
        if variant not in THRESHOLDS[project_id]:
            variant = 'default'
        undesired_threshold = THRESHOLDS[project_id].get(variant, \
            THRESHOLDS['default'])['undesired']
        thread_undesired_threshold = THRESHOLDS[project_id].get(variant, \
            THRESHOLDS['default'])['thread_undesired']
        unacceptable_threshold = THRESHOLDS[project_id].get(variant, \
            THRESHOLDS['default'])['unacceptable']
        thread_unacceptable_threshold = THRESHOLDS[project_id].get(variant, \
            THRESHOLDS['default'])['thread_unacceptable']
    except KeyError as key_error:
        print("{0} is not a supported project".format(key_error))
        sys.exit(1)

    # some tests may have higher noise margin and need different thresholds
    # when threshold override is used, use that for undesired and
    # use threshold_multiplier * undesired as unacceptable.
    # again, whether we use this override depends on the state of the ticket(s)
    override = get_override(test['name'], 'threshold', OVERRIDE_INFO)
    if override:
        #check_result['ticket'].extend(override['ticket'])
        (use_override_for_threshold, ticket_list) = \
            check_ticket_state(override['ticket'], jira_user, jira_password)
        check_result['ticket'].extend(ticket_list)
        if use_override_for_threshold:
            check_result['state'] = 'forced accept'
            check_result['notes'] += 'Override used for thresholds.'
            undesired_threshold = 1 - override['threshold']
            unacceptable_threshold = 1 - THRESHOLD_MULTIPLIER * override['threshold']
            thread_undesired_threshold = 1 - override['thread_threshold']
            thread_unacceptable_threshold = 1 - THRESHOLD_MULTIPLIER * override['thread_threshold']

    # we now have all the references and thresholds set up, as well moving the default
    # state to 'forced accept' when override is used, we can start the comparison
    # if noise data is available, take that into account for comparison
    # use the larger of threshold or noise to avoid false positive
    # when fixing PERF-595, we need to review noise-handling in all analysis scripts
    noise_levels = HISTORY.noise_levels(test['name'])
    worst_noise = max(noise_levels.values()) if (len(noise_levels.values()) == 0) else 0
    (failed, ratio, target) = compare_one_result_base(
        test['max'], reference['max'], worst_noise,
        NOISE_MULTIPLE, unacceptable_threshold)
    check_result['perf_ratio'] = 1 + ratio
    if failed:
        failed_reason = ' with test noise' if (target < unacceptable_threshold-0.0001)\
            else ''
        check_result['notes'] += 'Max throughput unacceptable '\
            + '(<{0:.2f} of baseline){1}\n'.format(1-target, failed_reason)
        if TEST_STATE[check_result['state']] < TEST_STATE['unacceptable']:
            check_result['state'] = 'unacceptable'
    else:
        (failed, ratio, target) = compare_one_result_base(
            test['max'], reference['max'], worst_noise,
            NOISE_MULTIPLE, undesired_threshold)
        if failed:
            failed_reason = ' with test noise' if (target < undesired_threshold-0.0001)\
                else ''
            check_result['notes'] += 'Max throughput undesired '\
                + '(<{0:.2f} of baseline){1}\n'.format(1-target, failed_reason)
            if TEST_STATE[check_result['state']] < TEST_STATE['undesired']:
                check_result['state'] = 'undesired'
    # check throughput at each thread level
    for level in (r for r in test["results"] if isinstance(test["results"][r], dict)):
        if level not in reference['results']:
            continue

        (failed, ratio, target) = compare_one_result_base(
            test['results'][level]['ops_per_sec'],
            reference['results'][level]['ops_per_sec'], noise_levels.get(level, 0),
            THREAD_NOISE_MULTIPLE, thread_unacceptable_threshold)
        if failed:
            failed_reason = ' with test noise' if (target < thread_unacceptable_threshold-0.0001)\
                else ''
            check_result['notes'] += 'Throughput at {0} unacceptable '.format(level)\
                + '(<{0:.2f} of baseline){1}\n'.format(1-target, failed_reason)
            if TEST_STATE[check_result['state']] < TEST_STATE['unacceptable']:
                check_result['state'] = 'unacceptable'
        else:
            (failed, ratio, target) = compare_one_result_base(
                test['results'][level]['ops_per_sec'],
                reference['results'][level]['ops_per_sec'], noise_levels.get(level, 0),
                THREAD_NOISE_MULTIPLE, thread_undesired_threshold)
            if failed:
                failed_reason = ' with test noise' \
                    if (target < thread_undesired_threshold-0.0001)\
                    else ''
                check_result['notes'] += 'Throughput at {0} undesired '.format(level)\
                    + '(<{0:.2f} of baseline){1}\n'.format(1-target, failed_reason)
                if TEST_STATE[check_result['state']] < TEST_STATE['undesired']:
                    check_result['state'] = 'undesired'

    return check_result


def repl_lag_check(test, threshold):
    ''' Iterate through all thread levels and flag a test if its
    max replication lag is higher than the threshold
    If there is no max lag information, consider the test 'pass '''
    check_result = {'state': 'pass', 'notes': '', 'ticket': []}
    for level in test['results']:
        if isinstance(test['results'][level], dict):
            max_lag = test['results'][level].get('replica_max_lag', 'NA')
            if max_lag != "NA":
                if float(max_lag) > threshold:
                    check_result['state'] = 'unacceptable'
                    check_result['notes'] += 'replica_max_lag ({0}) '.format(max_lag)\
                        + '> threshold({0}) seconds at {1} thread\n'.format(threshold, level)
    return check_result


# Other utility functions

def check_ticket_state(ticket_list, jira_user, jira_password):
    ''' Determine if we want to use override based on the states of the
    assoicated tickets. Use overrride if all tickets are in a terminal state
    (closed/resolved/won't fix). '''
    base_url = 'https://jira.mongodb.org/rest/api/latest/issue/'
    use_override = True
    ticket_display_list = []
    for ticket in ticket_list:
        url = base_url + ticket
        ticket_obj = {'name': ticket, 'status': ''}
        req = requests.get(url, auth=(jira_user, jira_password), verify=False)
        # Don't use override if any ticket is in a non-terminal state
        if req.status_code != 200:
            ticket_obj['status'] = 'failed jira query'
            use_override = False
        else:
            req_json = req.json()
            if 'fields' in req_json:
                ticket_status = req_json['fields']['status']['name']
                ticket_obj['status'] = ticket_status
                if ticket_status not in \
                        ('Closed', 'Resolved'):
                    use_override = False
        ticket_display_list.append(ticket_obj)
    return use_override, ticket_display_list


def update_state(current, new_data):
    ''' Update the current test info with new_data. Update the state to the
    more severe condition. Merge notes and ticket from new_data into current
    and add perf_ratio '''
    if TEST_STATE[new_data['state']] > TEST_STATE[current['state']]:
        current['state'] = new_data['state']
    current['notes'] += new_data.get('notes', '')
    current['ticket'].extend(new_data.get('ticket', []))
    if 'perf_ratio' in new_data:
        current['perf_ratio'] = new_data['perf_ratio']


def main(args):
    ''' Loop through and classify tests in a task into states used for
    dashboard '''
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--project_id", dest="project_id",
                        help="project_id for the test in Evergreen")
    parser.add_argument("--task_name", dest="task_name", help="task_name for"
                        " the test in Evergreen")
    parser.add_argument("-f", "--file", dest="hfile", help="path to json file"
                        " containing history data")
    parser.add_argument("-t", "--tagFile", dest="tfile", help="path to json"
                        " file containing tag data")
    parser.add_argument("--rev", dest="rev", help="revision to examine for"
                        " regressions")
    parser.add_argument("--refTag", nargs="+", dest="reference", help=
                        "Reference tag to compare against. Should be a valid"
                        " tag name")
    parser.add_argument("--overrideFile", dest="ofile",
                        help="File to read override information")
    parser.add_argument("--variant", dest="variant", help="Variant to lookup"
                        " in the override file")
    parser.add_argument("--task", dest="task", help="Task to lookup"
                        " in the override file")
    parser.add_argument("--jira-user", dest="jira_user", required=True, help=
                        "Jira account used to check ticket states. Incorrect"
                        "user/password may result in override information not"
                        "properly used")
    parser.add_argument("--jira-password", dest="jira_password", required=True,
                        help="Password for the Jira account. Incorrect"
                        " user/passowrd may result in override information not"
                        "properly used")
    parser.add_argument(
        "--dashboard-file", default="dashboard.json",
        help="File to write the dashboard JSON to.")
    ARGS = parser.parse_args(args)  # pylint: disable=invalid-name

    # Set up result histories from various files:
    # HISTORY - this series include the run to be checked, and previous or NDays
    # TAG_HISTORY - this is the series that holds the tag build as comparison target
    # OVERRIDE_INFO - this series has the override data to avoid false alarm or fatigues
    # The result histories are stored in global variables within this module as they
    # are accessed across many rules.
    global HISTORY, TAG_HISTORY, OVERRIDE_INFO # pylint: disable=global-statement
    (HISTORY, TAG_HISTORY, OVERRIDE_INFO) = read_histories(ARGS.variant, ARGS.task,\
                                                           ARGS.hfile, ARGS.tfile, ARGS.ofile)

    report = {'baselines':[]}
    for baseline in ARGS.reference:
        results = []
        report_for_baseline = {'version': baseline}
        # iterate through tests and check for regressions and other violations
        testnames = HISTORY.testnames()
        for test in testnames:
            result = {'test_file': test, 'state': 'pass', 'notes': '', \
                'ticket': [], 'perf_ratio': 1}
            to_check = HISTORY.series_at_revision(test, ARGS.rev)
            if to_check:
                update_state(result,
                             throughput_check(to_check, baseline,
                                              ARGS.project_id, ARGS.variant,
                                              ARGS.jira_user,
                                              ARGS.jira_password))
                update_state(result, repl_lag_check(to_check, REPL_LAG_THRESHOLD))
            else:
                result['state'] = 'no data'
                result['notes'] = 'No test results\n'
                print("\tno data at this revision, skipping")
                continue
            results.append(result)
        report_for_baseline['data'] = results
        report['baselines'].append(report_for_baseline)

    with open(ARGS.dashboard_file, "w") as dashboard_file:
        json.dump(report, dashboard_file, indent=4, separators=(',', ': '))

if __name__ == "__main__":
    main(sys.argv[1:])
