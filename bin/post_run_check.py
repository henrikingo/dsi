import argparse
import json
import sys
import itertools
from dateutil import parser
from datetime import timedelta, datetime

# Example usage:
# post_run_check.py -f history_file.json --rev 18808cd923789a34abd7f13d62e7a73fafd5ce5f
#         --project_id $pr_id --task_name $t_name
# Loads the history json file, and looks for regressions at the revision 18808cd...
# Evergreen project_id and task_name are used to uniquely identify the rule set to use
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
    previous = history.seriesAtNBefore(test['name'], test['revision'], 1)
    if not previous:
        print "\tno previous data, skipping"
        return {'PreviousCompare': 'pass'}
    else:
        return {'PreviousCompare': compare_throughputs(test, previous, "Previous", threshold, thread_threshold)}
    
def compare_to_NDays(test, threshold, thread_threshold):
    # check if there is a regression in the last week
    daysprevious = history.seriesAtNDaysBefore(test['name'], test['revision'], 7)
    if test['name'] in overrides['ndays']:
        print "Override in ndays for test %s" % test
        daysprevious = overrides['ndays'][test['name']]
    return {'NDayCompare': compare_throughputs(test, daysprevious, "NDays", threshold, thread_threshold)}
        
def compare_to_tag(test, threshold, thread_threshold):
    # if tag_history is undefined, skip this check completely
    if tag_history:
        reference = tag_history.seriesAtTag(test['name'], test['ref_tag'])
        if not reference : 
            print "Didn't get any data for test %s with baseline" % (test['name'])
        if test['name'] in overrides['reference']:
            print "Override in references for test %s" % test
            reference = overrides['reference'][test['name']]
        return {'BaselineCompare': compare_throughputs(test, reference, "Baseline Comparison",
                                                       threshold, thread_threshold)}
    else:
        return {}
    

# Failure and other condition checks


# project-specific rules

def sys_single(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.07, thread_threshold=0.07))
    to_return.update(compare_to_NDays(test, threshold=0.07, thread_threshold=0.07))
    to_return.update(compare_to_tag(test, threshold=0.07, thread_threshold=0.07))
    return to_return

def sys_replica(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.07, thread_threshold=0.07))
    to_return.update(compare_to_NDays(test, threshold=0.07, thread_threshold=0.07))
    to_return.update(compare_to_tag(test, threshold=0.07, thread_threshold=0.07))
    # max_lag check
    return to_return

def sys_shard(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.07, thread_threshold=0.07))
    to_return.update(compare_to_NDays(test, threshold=0.07, thread_threshold=0.07))
    to_return.update(compare_to_tag(test, threshold=0.07, thread_threshold=0.07))
    # max_lag check
    # possibly some check on whether load is balanced across shard
    return to_return

def longevity_shard(test):
    to_return = {}
    to_return.update(compare_to_previous(test, threshold=0.2, thread_threshold=0.2))
    # longevity tests are run once a week; 7-day check is not very useful
    to_return.update(compare_to_tag(test, threshold=0.2, thread_threshold=0.2))
    # max_lag check
    # possibly some check on whether load is balanced across shard
    return to_return

def unsupported(test):
    print "The (project_id, task_name) combination is not supported " \
      "for post_run_check.py"
    sys.exit(1)

# project_id and task_name uniquely identify the set of rules to check
# using a dictionary to help us choose the function with the right rules
check_rules = {
    'sys-perf': {
        'single_cluster_test': sys_single,
        'replica_cluster_test': sys_replica,
        'shard_cluster_test': sys_shard
        },
    'mongo-longevity': {
        'single_cluster_test': unsupported,
        'replica_cluster_test': unsupported,
        'shard_cluster_test': longevity_shard
        }
    }


        
'''
Utility functions and classes - these are functions and classes that load and manipulates
test results for various checks
'''

def get_json(filename):
    jf = open(filename, 'r')
    json_obj = json.load(jf)
    return json_obj


class History(object):
    def __init__(self, jsonobj):
        self._raw = sorted(jsonobj, key=lambda d: d["order"])
        self._noise = None

    def testnames(self):
        return set(list(itertools.chain.from_iterable([[z["name"] for z in c["data"]["results"]]
                                                       for c in self._raw])))

    def seriesAtRevision(self, testname, revision):
        s = self.series(testname)
        for result in s:
            if result["revision"] == revision:
                return result
        return None

    def seriesAtTag(self, testname, tagName):
        s = self.series(testname)
        for result in s:
            if result["tag"] == tagName:
                return result
        return None

    def seriesAtNBefore(self, testname, revision, n):
        """
            Returns the 'n' items in the series under the given test name that
            appear prior to the specified revision.
        """
        results = []
        older_build = 0
        s = self.series(testname)
        for result in s:
            if result["revision"] == revision:
                break
            older_build += 1
            results.append(result)

        if older_build > n:
            return results[-1*n:][0]
        return None

    def seriesAtNDaysBefore(self, testname, revision, n):
        """
            Returns the items in the series under the given test name that
            appear 'n' days prior to the specified revision.
        """
        results = {}
        # Date for this revision
        s = self.seriesAtRevision(testname, revision)
        if s==[]:
            return []
        refdate = parser.parse(s["create_time"]) - timedelta(days=n)

        s = self.series(testname)
        for result in s:
            if parser.parse(result["create_time"]) < refdate:
                results = result
        return results

    def series(self, testname):
        for commit in self._raw:
            # get a copy of the samples for those whose name matches the given testname
            matching = filter( lambda x: x["name"]==testname, commit["data"]["results"])
            if matching:
                result = matching[0]
                result["revision"] = commit["revision"]
                result["tag"] = commit["tag"]
                result["order"] = commit["order"]
                result["create_time"] = commit["create_time"]
                result["max"] = max(f["ops_per_sec"] for f in result["results"].values()
                                    if type(f) == type({}))
                result["threads"] = [f for f in result["results"] if type(result["results"][f])
                                     == type({})]
                yield result


def compare_one_throughput(this_one, reference, label, thread_level="max", threshold=0.07):
    # comapre one data point from result series this_one to reference at thread_level
    # if this_one is lower by threshold*reference return True

    print "checking %s" % (thread_level)
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
        print ("\tregression found on %s: drop from %.2f ops/sec (commit %s) to %.2f ops/sec for comparison %s. Diff is"
               " %.2f ops/sec (%.2f%%)" %
               (thread_level, ref, reference["revision"][:5], current, label, ref - current,
                100*(ref-current)/ref))
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

    # Check max throughput first
    if compare_one_throughput(this_one, reference, label, "max", threshold):
        failed = True
    # Check for regression on threading levels
    for (level, ops_per_sec) in (((r, this_one["results"][r]['ops_per_sec']) for r in
                                  this_one["results"] if type(this_one["results"][r]) == type({}))):
        if compare_one_throughput(this_one, reference, label, level,thread_threshold):
            failed = True
    if not failed:
        print "\tno regression against %s and githash %s" %(label, reference["revision"][:5])
        return 'pass'
    return 'fail'


def set_up_histories(variant, hfile, tfile, ofile):
    # Set up result histories from various files:
    # history - this series include the run to be checked, and previous or NDays
    # tag_history - this is the series that holds the tag build as comparison target
    # overrides - this series has the override data to avoid false alarm or fatigues
    # The result histories are stored in global variables within this module as they
    # are accessed across many rules. This funciton has to be called before running
    # the regression checks.
    global history, tag_history, overrides
    j = get_json(hfile)
    history = History(j)
    if tfile: 
        t = get_json(tfile)
        tag_history = History(t)
    else:
        tag_history = ""
    # Default empty override structure
    overrides = {'ndays' : {}, 'reference' : {}}
    if ofile:
        # Read the overrides file
        foverrides = get_json(ofile)
        # Is this variant in the overrides file?
        if variant in foverrides : 
            overrides = foverrides[variant]

                    


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
    set_up_histories(args.variant, args.hfile, args.tfile, args.ofile)
            
    failed = 0
    results = []

    # iterate through tests and check for regressions and other violations
    testnames = history.testnames()
    for test in testnames:
        result = {'test_file': test, 'exit_code': 0, 'elapsed' : 1, 'start': 1441227291.962453, 'end': 1441227293.428761}
        to_test = {'ref_tag': args.reference}
        t = history.seriesAtRevision(test, args.rev)
        if t:
            to_test.update(t)
            print "checking %s.." % (test)
            if len(to_test) == 1:
                print "\tno data at this revision, skipping"
                continue
            result.update(check_rules[args.project_id][args.task_name](to_test))
            if any(v == 'fail' for v in result.itervalues()):
                failed += 1
                result['status'] = 'fail'
            else:
                result['status'] = 'pass'
            results.append(result)

    report = {}
    report['failures'] = failed
    report['results'] = results

    reportFile = open('report.json', 'w')
    json.dump(report, reportFile, indent=4, separators=(',', ': '))
    if failed > 0 :
        sys.exit(1)
    else:
        sys.exit(0)

    

if __name__ == '__main__':
    main(sys.argv[1:])
