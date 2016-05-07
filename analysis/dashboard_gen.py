import itertools
from datetime import timedelta
import sys
import argparse
from dateutil import parser
import json
import StringIO

from util import read_histories, compare_one_result, log_header, get_override

# Example usage:
# post_run_check.py -f history_file.json --rev 18808cd923789a34abd7f13d62e7a73fafd5ce5f
#         --project_id $pr_id --variant $variant
# Loads the history json file, and looks for regressions at the revision 18808cd...
# Evergreen project_id and variant are used to uniquely identify the rule set to use
# Will exit with status code 1 if any regression is found, 0 otherwise.

# Output is written to dashboard.json
# Each test is classified into one of the following states
# pass
# undesired
# forced accept
# unacceptable
test_state = {
    'pass': 1,
    'undesired': 2,
    'forced accept': 3,
    'unacceptable': 4,
    'no data': 5
}

# project_id and variant uniquely identify the set of rules to check
# using a dictionary to help us choose the function with the right rules
thresholds = {
    'sys-perf': {
        'linux-oplog-compare': {
            'undesired': 0.1, 'thread_undesired': 0.2,
            'unacceptable': 0.15, 'thread_unaceeptable': 0.23
            }
        },
    'mongo-longevity': {
        'linux-wt-shard': {
            'undesired': 0.25, 'thread_undesired': 0.25,
            'unacceptable': 0.25, 'thread_unaceeptable': 0.25
            },
        'linux-mmapv1-shard': {
            'undesired': 0.25, 'thread_undesired': 0.25,
            'unacceptable': 0.25, 'thread_unaceeptable': 0.25
            }
        },
    'default': {
        'undesired': 0.08, 'thread_undesired': 0.12,
        'unacceptable': 0.12, 'thread_unaceeptable': 0.18
        }
    }



'''
Rules section -
    throughput_check retrun(state, notes, tickets, perf_ratio)
    replica_lag_check return(state, notes, tickets)
'''

# Common regression rules
def throughput_check(test, ref_tag, project_id, variant):
    ''' compute throughput ratios for all points in result series this_one
     over reference. Classify a test into a state based on the ratios.

     Use different thresholds for max throughput, and per-thread comparisons
     retrun (state, notes, perf_ratio, tickets)
    '''
    state = 'pass'
    notes = ''
    tickets = []
    perf_ratio = 1

    # if tag_history is undefined, skip this check completely
    if tag_history:
        reference = tag_history.series_at_tag(test['name'], ref_tag)
        if not reference:
            print "        no reference data for test %s with baseline" % (test['name'])
            return (state, notes, tickets, perf_ratio)
        tempdict = get_override(test['name'], 'reference', overrides)
        if tempdict:
            reference = tempdict
            tickets.extend(reference['ticket'])
    # Don't do a comparison if the reference data is missing
    if not reference:
        print "        no reference data for test %s with baseline" % (test['name'])
        return (state, notes, tickets, perf_ratio)

    print reference
    # get the default thresholds to use
    try:
        threshold = thresholds[project_id].get(variant, thresholds['default'])['unacceptable']
        thread_threshold = thresholds[project_id].get(variant, thresholds['default'])['unacceptable']
    #    except Exception as e:
    except Exception as e:
        print "{0} is not a supported project".format(e)
        sys.exit(1)

    # some tests may have higher noise margin and need different thresholds
    # this info is kept as part of the override file
    if get_override(test['name'], 'threshold', overrides):
        tempdict = get_override(test['name'], 'threshold', overrides)
        tickets.extend(tempdict['ticket'])
        threshold = tempdict['threshold']
        thread_threshold = tempdict['thread_threshold']

    # Compute the ratios for max throughput achieved
    ratio_at_max = 1 if reference['max'] == 0 else test['max']/reference['max']
    perf_ratio = worst_ratio = ratio_at_max
    worst_thread = 'max'
    for level in (r for r in test["results"] if isinstance(test["results"][r], dict)):
        thread_ratio = 1 if reference['results'][level]['ops_per_sec'] ==0 \
            else test['results'][level]['ops_per_sec']/reference['results'][level]['ops_per_sec']
        if thread_ratio < worst_ratio:
            worst_ratio = thread_ratio
            worst_thread = level
    # Use throughput ratios to determine the state of the test
    if worst_ratio < 1 - thread_threshold:
        if test_state[state] < test_state['unacceptable']:
            notes += "Max_throughput out of range\n"
            state = 'unacceptable'
    if worst_ratio < 1 - thread_threshold:
        if test_state[state] < test_state['unacceptable']:
            notes += "Throughput at {0:} thread out of range\n".format(worst_thread)
            state = 'unacceptable'
    return (state, notes, tickets, perf_ratio)


# Failure and other condition checks
def replica_lag_check(test, threshold):
    # Iterate through all thread levels and flag a test if its
    # max replication lag
    # is higher than the threshold
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
        total_lag_entry += lag_entry
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
        print("        replica_lag under threshold (%s) seconds" % threshold)
    return {'Replica_lag_check': status}


"""
For each test in the result, generate data that will be used by the dashboard.
"""
def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_id", dest="project_id", help="project_id for the test in Evergreen")
    parser.add_argument("--task_name", dest="task_name", help="task_name for the test in Evergreen")
    parser.add_argument("-f", "--file", dest="hfile", help="path to json file containing"
                        "history data")
    parser.add_argument("-t", "--tagFile", dest="tfile", help="path to json file containing"
                        "tag data")
    parser.add_argument("--rev", dest="rev", help="revision to examine for regressions")
    parser.add_argument("--refTag", dest="reference", help=
                        "Reference tag to compare against. Should be a valid tag name")
    parser.add_argument("--overrideFile", dest="ofile", help="File to read for comparison override information")
    parser.add_argument("--variant", dest="variant", help="Variant to lookup in the override file")

    args = parser.parse_args()

    # Set up result histories from various files:
    # history - this series include the run to be checked, and previous or NDays
    # tag_history - this is the series that holds the tag build as comparison target
    # overrides - this series has the override data to avoid false alarm or fatigues
    # The result histories are stored in global variables within this module as they
    # are accessed across many rules.
    global history, tag_history, overrides
    (history, tag_history, overrides) = read_histories(args.variant,
        args.hfile, args.tfile, args.ofile)

    failed = 0
    results = []
    # replication lag table lines
    global replica_lag_line
    replica_lag_line = []

    report = {'baselines':[]}
    report_for_baseline = {'version': args.reference}
    # iterate through tests and check for regressions and other violations
    testnames = history.testnames()
    for test in testnames:
        result = {'test_file': test, 'state': 'NA', 'notes': '',
            'tickets': [], 'perf_ratio': 1}
        t = history.series_at_revision(test, args.rev)
        if t:
            if t is None:
                print "\tno data at this revision, skipping"
                continue
            # Use project_id and variant to identify the rule set
            # May want to use task_name for further differentiation
            (result['state'], cnotes, ctickets, cratio) = throughput_check(t,
                    args.reference, args.project_id, args.variant)
            print ctickets
            try:
            #result.update(throughput_check(to_test, args.reference, \
            #    args.project_id, args.variant))
                (result['state'], cnotes, ctickets, cratio) = throughput_check(t,
                    args.reference, args.project_id, args.variant)
                result['notes'] += cnotes
                result['tickets'].extend(ctickets)
                result['perf_ratio'] = cratio
            except Exception as e:
                print "an exception has occured..."
                print e
                sys.exit(1)
            results.append(result)
    report_for_baseline['data'] = results
    # should create an outerloop to go through all baselines we care
    report['baselines'].append(report_for_baseline)

    reportFile = open('dashboard.json', 'w')
    json.dump(report, reportFile, indent=4, separators=(',', ': '))
    if failed > 0 :
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main(sys.argv[1:])
