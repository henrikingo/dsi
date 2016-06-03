#!/bin/env python2.7
'''
Iterate through tests to evaluate their states to display in the performance
dashboard against the specified baselines. Output is written to dashboard.json
which in turn is sent to the Evergreen database.

Example usage:
 dashboard_gen.py -f history_file.json --rev 18808cd923789a34abd7f13d62e7a73fafd5ce5f
         --project_id $pr_id --variant $variant
'''
from __future__ import print_function
import sys
import argparse
import json
import requests
from util import read_histories, get_override


# tests are classified into one of the following states
# When combining states from multiple checks, the highest valued state wins
test_state = {
    'pass': 1,
    'forced accept': 2,
    'undesired': 3,
    'unacceptable': 4,
    'no data': 5
}

# project_id and variant uniquely identify the set of rules to check
# using a dictionary to help us choose the function with the right rules
thresholds = {
    'sys-perf': {
        'linux-oplog-compare': {
            'undesired': 0.1, 'thread_undesired': 0.2,
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
        'undesired': 0.08, 'thread_undesired': 0.12,
        'unacceptable': 0.12, 'thread_unacceptable': 0.18
        }
    }
# if only one threshold is defined, such as in the case of
# using a treshold_override, we use that for undesired and use
# a multiplier to define the unacceptable
threshold_multiplier = 1.5


'''
Checks section -
    All checks return a dictionary that contains information used by
    the dashboard. The information include state, notes, tickets
    and perf_ratio. A check may return only a subset of the information
    that is relevant to the conditions it checks.
'''

def throughput_check(test, ref_tag, project_id, variant):
    ''' compute throughput ratios for all points in result series this_one
     over reference. Classify a test into a result['state'] based on the ratios.
     Use different thresholds for max throughput, and per-thread comparisons. '''
    check_result = {'state': 'pass', 'notes': '', 'tickets': [],
                    'perf_ratio': 1}

    # if tag_history is undefined, skip this check completely
    if tag_history:
        reference = tag_history.series_at_tag(test['name'], ref_tag)
        # Don't do a comparison if the reference data is missing
        if not reference:
            check_result['notes'] += "No reference data for test in baseline\n"
            return check_result
        # throughput override and ticket handling
        override = get_override(test['name'], 'reference', override_info)
        if override:
            check_result['tickets'].extend(override['ticket'])
            if use_override(override['ticket']):
                reference = override

    # get the thresholds to use
    try:
        undesired_target = 1 - thresholds[project_id].get(variant, \
            thresholds['default'])['undesired']
        thread_undesired_target = 1 - thresholds[project_id].get(variant, \
            thresholds['default'])['thread_undesired']
        unacceptable_target = 1 - thresholds[project_id].get(variant, \
            thresholds['default'])['unacceptable']
        thread_unacceptable_target = 1 - thresholds[project_id].get(variant, \
            thresholds['default'])['thread_unacceptable']
    except KeyError as key_error:
        print("{0} is not a supported project".format(key_error))
        sys.exit(1)
    # some tests may have higher noise margin and need different thresholds
    # this info is kept as part of the override file
    # when threshold override is used, use that for undesired and
    # use threshold_multiplier * undesired as unacceptable.
    # again, whether we use this override depends on the state of the tickets
    override = get_override(test['name'], 'threshold', override_info)
    if override:
        check_result['tickets'].extend(override['ticket'])
        if use_override(override['ticket']):
            undesired_target = 1 - override['threshold']
            unacceptable_target = 1 - threshold_multiplier * override['threshold']
            thread_undesired_target = 1 - override['thread_threshold']
            thread_unacceptable_target = 1 - threshold_multiplier * override['thread_threshold']

    # Compute the ratios for max throughput achieved
    ratio_at_max = 1 if reference['max'] == 0 else test['max']/reference['max']
    check_result['perf_ratio'] = ratio_at_max
    num_level = worst_ratio = 0
    for level in (r for r in test["results"] if isinstance(test["results"][r], dict)):
        # Skip the max level beause we already calculated that
        if level != 'max':
            num_level += 1
            thread_ratio = 1 if reference['results'][level]['ops_per_sec'] == 0 \
                else test['results'][level]['ops_per_sec']\
                    /reference['results'][level]['ops_per_sec']
            if thread_ratio <= worst_ratio or worst_ratio == 0:
                worst_ratio = thread_ratio
                worst_thread = level

    # only use the tigher threshold at max if more than one thread level
    # was reported. log only the most severe condition.
    if num_level > 1:
        if ratio_at_max < unacceptable_target:
            check_result['notes'] += 'Max throughput unacceptable '\
                + '(<{0:1.2f} of baseline)\n'.format(unacceptable_target)
            check_result['state'] = 'unacceptable'
        elif ratio_at_max < undesired_target:
            check_result['notes'] += 'Max throughput undesired '\
                + '(<{0:1.2f} of baseline)\n'.format(undesired_target)
            check_result['state'] = 'undesired'
        if worst_ratio < thread_unacceptable_target:
            check_result['notes'] += 'Throughput at {0} '.format(worst_thread)\
                + 'unacceptable (<{0:1.2f} of baseline)\n'.format(thread_unacceptable_target)
            if test_state[check_result['state']] < test_state['unacceptable']:
                check_result['state'] = 'unacceptable'
        elif worst_ratio < thread_undesired_target:
            check_result['notes'] += 'Throughput at {0} '.format(worst_thread)\
                + 'undesired (<{0:1.2f} of baseline)\n'.format(thread_undesired_target)
            if test_state[check_result['state']] < test_state['undesired']:
                check_result['state'] = 'undesired'

    return check_result

def repl_lag_check(test, threshold):
    ''' Iterate through all thread levels and flag a test if its
    max replication lag is higher than the threshold
    If there is no max lag information, consider the test 'pass '''
    check_result = {'state': 'pass', 'notes': '', 'tickets': []}
    for level in test['results']:
        max_lag = test['results'][level].get('replica_max_lag', 'NA')
        if max_lag != "NA":
            if float(max_lag) > threshold:
                check_result['state'] = 'unacceptable'
                check_result['notes'] += 'replica_max_lag ({0}) '.format(max_lag)\
                    + '> threshold({0}) seconds at {1} thread\n'.format(threshold, level)
    return check_result


''' Other utility functions '''

def use_override(ticket_list):
    ''' Determine if we want to use override based on the states of the assoicated tickets.
    Use overrride if all tickets are in a terminal state (closed/resolved/won't fix). '''
    base_url = 'https://jira.mongodb.org/rest/api/latest/issue/'
    for ticket in ticket_list:
        url = base_url + ticket
        #req = requests.get(url, auth=('user', 'pass'))
        req = requests.get(url)
        req_json = req.json()
        if 'fields' in req_json:
            if req_json['fields']['status']['name'] not in ('closed', 'resolved', 'wont fix'):
                return False
    return True

def update_state(current, new_data):
    ''' Update the current test info with new_data. Update the state to the
    more severe condition. Merge notes and tickets from new_data into current
    and add perf_ratio '''
    if test_state[new_data['state']] > test_state[current['state']]:
        current['state'] = new_data['state']
    current['notes'] += new_data.get('notes', '')
    current['tickets'].extend(new_data.get('tickets', []))
    if 'perf_ratio' in new_data:
        current['perf_ratio'] = new_data['perf_ratio']


def main(args):
    ''' Loop through and classify tests in a task into states used for dashboard '''
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_id", dest="project_id",
                        help="project_id for the test in Evergreen")
    parser.add_argument("--task_name", dest="task_name", help="task_name for the test in Evergreen")
    parser.add_argument("-f", "--file", dest="hfile", help="path to json file containing"
                        "history data")
    parser.add_argument("-t", "--tagFile", dest="tfile", help="path to json file containing"
                        "tag data")
    parser.add_argument("--rev", dest="rev", help="revision to examine for regressions")
    parser.add_argument("--refTag", nargs="+", dest="reference", help=
                        "Reference tag to compare against. Should be a valid tag name")
    parser.add_argument("--overrideFile", dest="ofile",
                        help="File to read for comparison override information")
    parser.add_argument("--variant", dest="variant", help="Variant to lookup in the override file")

    args = parser.parse_args()

    # Set up result histories from various files:
    # history - this series include the run to be checked, and previous or NDays
    # tag_history - this is the series that holds the tag build as comparison target
    # override_info - this series has the override data to avoid false alarm or fatigues
    # The result histories are stored in global variables within this module as they
    # are accessed across many rules.
    global history, tag_history, override_info
    (history, tag_history, override_info) = read_histories(args.variant, \
        args.hfile, args.tfile, args.ofile)

    report = {'baselines':[]}
    for baseline in args.reference:
        results = []
        report_for_baseline = {'version': baseline}
        # iterate through tests and check for regressions and other violations
        testnames = history.testnames()
        for test in testnames:
            result = {'test_file': test, 'state': 'pass', 'notes': '', \
                'tickets': [], 'perf_ratio': 1}
            to_check = history.series_at_revision(test, args.rev)
            if to_check:
                update_state(result, throughput_check(to_check, baseline, \
                    args.project_id, args.variant))
                update_state(result, repl_lag_check(to_check, 10))
            else:
                result['state'] = 'no data'
                result['notes'] = 'No test results\n'
                print("\tno data at this revision, skipping")
                continue
            results.append(result)
        report_for_baseline['data'] = results
        report['baselines'].append(report_for_baseline)

    report_file = open('dashboard.json', 'w')
    json.dump(report, report_file, indent=4, separators=(',', ': '))


if __name__ == '__main__':
    main(sys.argv[1:])
