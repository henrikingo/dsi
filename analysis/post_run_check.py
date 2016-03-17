import argparse
from datetime import timedelta, datetime
from dateutil import parser
import json
import itertools
import os
import re
import StringIO
import sys

from evergreen.history import History
from evergreen.util import read_histories

# Example usage:
# post_run_check.py -f history_file.json --rev 18808cd923789a34abd7f13d62e7a73fafd5ce5f
#         --project_id $pr_id --variant $variant
# Loads the history json file, and looks for regressions at the revision 18808cd...
# Evergreen project_id and variant are used to uniquely identify the rule set to use
# Will exit with status code 1 if any regression is found, 0 otherwise.


'''
Rules section - types of rules are:
1. Common regression rules
2. Additional checks that look for failures or other undesirable conditions
3. Project specific rules, which calls rules of types 1 & 2
   with project-specific rule sets and thresholds/parameters
'''

# Common regression rules

def compare_to_previous(test, threshold, thread_threshold):
    previous = history.series_at_n_before(test['name'], test['revision'], 1)
    if not previous:
        print "        no previous data, skipping"
        return {'PreviousCompare': 'pass'}
    else:
        return {'PreviousCompare': compare_throughputs(test, previous, "Previous", threshold, thread_threshold)}

def compare_to_NDays(test, threshold, thread_threshold):
    # check if there is a regression in the last week
    daysprevious = history.series_at_n_days_before(test['name'], test['revision'], 7)
    if not daysprevious:
        print "        no reference data for test %s with NDays" % (test['name'])
        return {}
    if test['name'] in overrides['ndays']:
        try:
            overrideTime = parser.parse(overrides['ndays'][test['name']]['create_time'])
            thisTime = parser.parse(test['create_time'])
            # I hate that this 7 is a constant. Copying constant from first line in function
            if (overrideTime < thisTime) and ((overrideTime + timedelta(days=7)) >= thisTime) :
                daysprevious = overrides['ndays'][test['name']]
                print "        using override in ndays for test %s" % test['name']
            else :
                print "Out of date override found for ndays. Not using"
        except KeyError as e:
            print >> sys.stderr, "Key error accessing overrides for ndays. Key {0} doesn't exist for test {1}".format(str(e), test['name'])

    return {'NDayCompare': compare_throughputs(test, daysprevious, "NDays", threshold, thread_threshold)}

def compare_to_tag(test, threshold, thread_threshold):
    # if tag_history is undefined, skip this check completely
    if tag_history:
        reference = tag_history.series_at_tag(test['name'], test['ref_tag'])
        if not reference:
            print "        no reference data for test %s with baseline" % (test['name'])
        if test['name'] in overrides['reference']:
            print "        using override in references for test %s" % test
            reference = overrides['reference'][test['name']]
        return {'BaselineCompare': compare_throughputs(test, reference, "Baseline",
                                                       threshold, thread_threshold)}
    else:
        return {}


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
        print("        replica_lag under threshold (%s) seconds" % threshold)
    return {'Replica_lag_check': status}



# project-specific rules

def sys_linux_1_node_replSet(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_NDays(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    return to_return

def sys_linux_standalone(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_NDays(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    return to_return

def sys_linux_3_shard(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_NDays(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    # max_lag check
    to_return.update(replica_lag_check(test, threshold=10))
    # possibly some check on whether load is balanced across shard
    return to_return

def sys_linux_3_node_replSet(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_NDays(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    # max_lag check
    to_return.update(replica_lag_check(test, threshold=10))
    return to_return

def sys_linux_oplog_compare(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.1, thread_threshold=0.2))
    to_return.update(compare_to_NDays(test, threshold=0.1, thread_threshold=0.2))
    to_return.update(compare_to_tag(test, threshold=0.1, thread_threshold=0.2))
    return to_return

def sys_linux_standlone_c3_2xlarge(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_NDays(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    return to_return

def sys_linux_standlone_c3_4xlarge(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_NDays(test, threshold=0.08, thread_threshold=0.12))
    to_return.update(compare_to_tag(test, threshold=0.08, thread_threshold=0.12))
    return to_return

def longevity_linux_wt_shard(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.25, thread_threshold=0.25))
    # longevity tests are run once a week; 7-day check is not very useful
    to_return.update(compare_to_tag(test, threshold=0.25, thread_threshold=0.25))
    # max_lag check
    to_return.update(replica_lag_check(test, threshold=10))
    # possibly check on
    return to_return

def longevity_linux_wt_shard_csrs(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.25, thread_threshold=0.25))
    # longevity tests are run once a week; 7-day check is not very useful
    to_return.update(compare_to_tag(test, threshold=0.25, thread_threshold=0.25))
    # max_lag check
    to_return.update(replica_lag_check(test, threshold=10))
    # possibly check on
    return to_return

def longevity_linux_mmapv1_shard(test):
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
check_rules = {
    'sys-perf': {
        'linux-1-node-replSet': sys_linux_1_node_replSet,
        'linux-standalone': sys_linux_standalone,
        'linux-3-shard': sys_linux_3_shard,
        'linux-3-node-replSet': sys_linux_3_node_replSet,
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

def compare_one_throughput(this_one, reference, label, thread_level="max", threshold=0.07):
    # comapre one data point from result series this_one to reference at thread_level
    # if this_one is lower by threshold*reference return True

    # Don't do a comparison if the reference data is missing
    if not reference:
        return False

    if thread_level == "max":
        ref = reference["max"]
        current = this_one["max"]
    else:
        # Don't do a comparison if the thread data is missing
        if not thread_level in reference["results"].keys():
            return False
        ref = reference["results"][thread_level]['ops_per_sec']
        current = this_one["results"][thread_level]['ops_per_sec']

    delta = threshold * ref
    if ref - current >= delta:
        diff_percent = 100*(current-ref)/ref
        if label == "Baseline":
            print ("   ---> regression found on %s: drop from %.2f ops/sec (%s) to %.2f "
                   "ops/sec for comparison %s. Diff is %.2f ops/sec (%.2f%%)"
                   %(thread_level, ref, reference["tag"], current, label, ref - current, diff_percent))
            regression_line.append((this_one["name"], label, reference["tag"],
                                    thread_level, ref, current, diff_percent))
        else:
            print ("   ---> regression found on %s: drop from %.2f ops/sec (%s) to %.2f "
                   "ops/sec for comparison %s. Diff is %.2f ops/sec (%.2f%%)"
                   %(thread_level, ref, reference["tag"], current, label,
                     ref - current, diff_percent))
            regression_line.append((this_one["name"], label, reference["revision"][:5],
                                    thread_level, ref, current, diff_percent))
        return True
    else:
        return False


def compare_throughputs(this_one, reference, label, threshold=0.07, thread_threshold=0.1):
    # comapre all points in result series this_one to reference
    # Use different thresholds for max throughput, and per-thread comparisons
    # return 'fail' if any of this_one is lower in any of the comparison
    # otherwise return 'pass'
    failed = False

    # Don't do a comparison if the reference data is missing
    if not reference:
        return 'pass'

    # some tests may have higher noise margin and need different thresholds
    # this info is kept as part of the override file
    if 'threshold' in overrides:
        if this_one['name'] in overrides['threshold']:
            try:
                threshold = overrides['threshold'][this_one['name']]['threshold']
                thread_threshold = overrides['threshold'][this_one['name']]['thread_threshold']
            except KeyError as e:
                print >> sys.stderr, "Threshold overrides not properly defined. Key {0} doesn't exist for test {1}".format(str(e), test['name'])

    # Check max throughput first
    if compare_one_throughput(this_one, reference, label, "max", threshold):
        failed = True
    # Check for regression on threading levels
    for (level, ops_per_sec) in (((r, this_one["results"][r]['ops_per_sec']) for r in
                                  this_one["results"] if type(this_one["results"][r]) == type({}))):
        if compare_one_throughput(this_one, reference, label, level,thread_threshold):
            failed = True
    if not failed:
        if label == "Baseline":
            print "        no regression against %s (%s) above thresholds(%s, %s)" %(label, reference["tag"], threshold, thread_threshold)
        else:
            print "        no regression against %s (%s) above thresholds(%s, %s)" %(label, reference["revision"][:5], threshold, thread_threshold)
        return 'pass'
    return 'fail'

"""
For each test in the result, we call the variant-specific functions to check for
regressions and other conditions. We keep a count of failed tests in 'failed'.
We also maintain a list of pass/fail conditions for all rules
for every tests, which gets dumped into a report file at the end.
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
    (history, tag_history, overrides) = read_histories(args.variant, args.hfile, args.tfile, args.ofile)

    failed = 0
    results = []
    # regression summary table lines
    global regression_line
    regression_line = []
    # replication lag table lines
    global replica_lag_line
    replica_lag_line = []

    # iterate through tests and check for regressions and other violations
    testnames = history.testnames()
    for test in testnames:
        result = {'test_file': test, 'exit_code': 0, 'log_raw': '\n'}
        to_test = {'ref_tag': args.reference}
        t = history.series_at_revision(test, args.rev)
        if t:
            to_test.update(t)
            result["start"] = t.get("start", 0)
            result["end"] = t.get("end", 1)
            print "=============================="
            print "checking %s.." % (test)
            if len(to_test) == 1:
                print "\tno data at this revision, skipping"
                continue
            # Use project_id and variant to identify the rule set
            # May want to use task_name for further differentiation
            try:
                # Redirect stdout to log_stdout to capture per test log
                real_stdout = sys.stdout
                log_stdout = StringIO.StringIO()
                sys.stdout = log_stdout
                result.update(check_rules[args.project_id][args.variant](to_test))
                # Store log_stdout in log_raw
                test_log = log_stdout.getvalue()
                result['log_raw'] += test_log
                # Restore stdout (important) and print test_log to it
                sys.stdout = real_stdout
                print test_log
            except Exception as e:
                # Need to restore and print stdout in case of Exception
                test_log = log_stdout.getvalue()
                sys.stdout = real_stdout
                print test_log
                print "The (project_id, variant) combination is not supported " \
                    "in post_run_check.py: {0}".format(str(e))
                print sys.exc_info()[0]
                sys.exit(1)
            if any(v == 'fail' for v in result.itervalues()):
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

    # use the stderr to print regression summary table
    # a similar error summary table can be added for error conditions
    if len(regression_line) > 0:
        print >> sys.stderr, "\n=============================="
        print >> sys.stderr, "Regression Summary:"
        printing_test = ""
        for line in regression_line:
            if line[0] != printing_test:
                printing_test = line[0]
                print >> sys.stderr, "\n%s" % printing_test
                print >> sys.stderr, ("%10s|%16s|%7s|%11s|%11s|%11s" %
                                      ("Violation", "Compared_to", "Thread",
                                       "Target", "Achieved", "delta(%)") )
                print >> sys.stderr, "-"*10 + "+" + "-"*16 + "+" + "-"*7 + "+" + "-"*11 + "+" + "-"*11 + "+" + "-"*11
            print >> sys.stderr, ("%10s|%16s|%7s|%11.2f|%11.2f|%11.2f" % line[1:])

    # use the stderr to print replica_lag table
    if len(replica_lag_line) > 0:
        print >> sys.stderr, "\n=============================="
        print >> sys.stderr, "Replication Lag Summary:"
        printing_test = ""
        for line in replica_lag_line:
            if line[0] != printing_test:
                printing_test = line[0]
                print >> sys.stderr, "\n%s" % printing_test
                print >> sys.stderr, ("%10s|%16s|%16s|%16s" %
                                      ("Thread", "Avg_lag", "Max_lag", "End_of_test_lag"))
                print >> sys.stderr, "-"*10 + "+" + "-"*16 + "+" + "-"*16 + "+" + "-"*16
            print_line = '{0:>10}'.format(line[1])
            for x in line[2:]:
                p = '|{0:16.2f}'.format(x) if isinstance(x, float) else '|{0:>16}'.format(x)
                print_line = print_line + p
            print >> sys.stderr, print_line

    # flush stderr to the log file
    sys.stderr.flush()

    reportFile = open('report.json', 'w')
    json.dump(report, reportFile, indent=4, separators=(',', ': '))
    if failed > 0 :
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main(sys.argv[1:])
