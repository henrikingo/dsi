from datetime import timedelta
import sys
import argparse
from dateutil import parser
import json

from evergreen.util import read_histories, compare_one_result, log_header

# Example usage:
# perf_regression_check.py -f history_file.json --rev 18808cd923789a34abd7f13d62e7a73fafd5ce5f
# Loads the history json file, and looks for regressions at the revision 18808cd...
# Will exit with status code 1 if any regression is found, 0 otherwise.

def compareResults(this_one, reference, threshold, label,
                   noise_levels={}, noise_multiple=1, thread_threshold=None,
                   thread_noise_multiple=None, using_override=None):
    '''
    Take two result series and compare them to see if they are acceptable.
    Return true if failed, and false if pass
    '''

    failed = False
    log = ""
    if not reference:
        return (failed, "No reference data for " + label)
    # Default thread_threshold to the same as the max threshold
    if  not thread_threshold:
        thread_threshold = threshold
    if not thread_noise_multiple:
        thread_noise_multiple = noise_multiple

    # Check max throughput first
    noise = 0
    # For the max throughput, use the max noise across the thread levels as the noise parameter
    if len(noise_levels.values()) > 0:
        noise = max(noise_levels.values())
    result = compare_one_result(this_one, reference, label, "max",
                                noise_level=noise,
                                noise_multiple=noise_multiple,
                                default_threshold=threshold,
                                using_override=using_override)
    log += result[1] + '\n'
    if result[0]: # Comparison failed
        failed = True
    # Check for regression on threading levels
    for level in (r for r in this_one["results"] if
                  isinstance(this_one["results"][r], dict)):
        noise = 0
        if level in noise_levels:
            noise = noise_levels[level]
        result = compare_one_result(this_one, reference, label, level,
                                    noise_level=noise,
                                    noise_multiple=thread_noise_multiple,
                                    default_threshold=thread_threshold,
                                    using_override=using_override)
        log += result[1] + '\n'
        if result[0]: # Comparison failed
            failed = True

    return (failed, log)



def main(args):
    argParser = argparse.ArgumentParser()
    argParser.add_argument("-f", "--file", dest="file", help="path to json file containing"
                        "history data")
    argParser.add_argument("-t", "--tagFile", dest="tfile", help="path to json file containing"
                        "tag data")
    argParser.add_argument("--rev", dest="rev", help="revision to examine for regressions")
    argParser.add_argument("--ndays", default=7, type=int, dest="ndays", help="Check against"
                        "commit from n days ago.")
    argParser.add_argument("--threshold", default=0.05, type=float, dest="threshold", help=
                        "Don't flag an error if throughput is less than 'threshold'x100 percent off")
    argParser.add_argument("--noiseLevel", default=1, type=float, dest="noise", help=
                        "Don't flag an error if throughput is less than 'noise' times the computed noise level off")
    argParser.add_argument("--threadThreshold", default=0.1, type=float, dest="thread_threshold", help=
                        "Don't flag an error if thread level throughput is more than"
                        "'thread_threshold'x100 percent off")
    argParser.add_argument("--threadNoiseLevel", default=2, type=float, dest="threadNoise", help=
                        "Don't flag an error if thread level throughput is less than 'noise' times the computed noise level off")
    argParser.add_argument("--refTag", dest="reference", help=
                        "Reference tag to compare against. Should be a valid tag name")
    argParser.add_argument("--overrideFile", dest="overrideFile", help="File to read for comparison override information")
    argParser.add_argument("--variant", dest="variant", help="Variant to lookup in the override file")

    args = argParser.parse_args()
    (history, tag_history, overrides) = read_histories(args.variant, args.file, args.tfile,
                                                       args.overrideFile)
    testnames = history.testnames()
    failed = 0

    results = []

    for test in testnames:
        # The first entry is valid. The rest is dummy data to match the existing format
        result = {'test_file' : test, 'exit_code' : 0, 'elapsed' : 5, 'start': 1441227291.962453,
                  'end': 1441227293.428761, 'log_raw' : ''}
        this_one = history.series_at_revision(test, args.rev)
        testFailed = False
        result['log_raw'] = log_header(test)

        if not this_one:
            print "\tno data at this revision, skipping"
            continue

        #If the new build is 10% lower than the target (3.0 will be
        #used as the baseline for 3.2 for instance), consider it
        #regressed.
        previous = history.series_at_n_before(test, args.rev, 1)
        if not previous:
            print "\tno previous data, skipping"
            continue
        cresult = compareResults(this_one, previous, args.threshold,
                                 "Previous",
                                 history.noise_levels(test),
                                 args.noise, args.thread_threshold,
                                 args.threadNoise, False)
        result['PreviousCompare'] = cresult[0]
        result['log_raw'] += cresult[1] + '\n'
        if cresult[0]:
            testFailed = True

        daysprevious = history.series_at_n_days_before(test, args.rev, args.ndays)
        if daysprevious:
            using_override = []
            try:
                if test in overrides['ndays']:
                    overrideTime = parser.parse(overrides['ndays'][test]['create_time'])
                    thisTime = parser.parse(this_one['create_time'])
                    if (overrideTime < thisTime) and ((overrideTime + timedelta(days=args.ndays)) >= thisTime):
                        daysprevious = overrides['ndays'][test]
                        using_override.append("reference")
                        print "Override in ndays for test %s" % test
                    else:
                        print "Out of date override found for ndays. Not using"
            except KeyError as e:
                print "Key error accessing overrides for ndays. Key {0} doesn't exist for test {1}".format(str(e), test)

            cresult = compareResults(this_one, daysprevious,
                                     args.threshold, "NDays",
                                     history.noise_levels(test),
                                     args.noise,
                                     args.thread_threshold,
                                     args.threadNoise, using_override=using_override)
            result['NDayCompare'] = cresult[0]
            result['log_raw'] += cresult[1] + '\n'
            if cresult[0]:
                testFailed = True
        else:
            print "\tWARNING: no nday data, skipping"

        if tag_history:
            reference = tag_history.series_at_tag(test, args.reference)
            using_override = []
            if not reference:
                print "Didn't get any data for test %s with baseline %s" % (test, args.reference)
            if test in overrides['reference']:
                print "Override in references for test %s" % test
                using_override.append("reference")
                reference = overrides['reference'][test]
            cresult = compareResults(this_one, reference,
                                     args.threshold, "Baseline",
                                     history.noise_levels(test),
                                     args.noise,
                                     args.thread_threshold,
                                     args.threadNoise,
                                     using_override=using_override)
            result['BaselineCompare'] = cresult[0]
            result['log_raw'] += cresult[1] + '\n'
            if cresult[0] :
                testFailed = True
        else:
            print "\tWARNING: no reference data, skipping"

        print result['log_raw']
        if testFailed:
            result['status'] = 'fail'
            failed += 1
        else:
            result['status'] = 'pass'
        results.append(result)

    report = {}
    report['failures'] = failed
    report['results'] = results

    reportFile = open('report.json', 'w')
    json.dump(report, reportFile, indent=4, separators=(',', ': '))
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


class TestResult:
    def __init__(self, json):
        self._raw = json

    #def max(self):

if __name__ == '__main__':
    main(sys.argv[1:])
