"""Module for handling evergreen histories."""

from __future__ import print_function
import itertools
from datetime import timedelta
from dateutil import parser


class History(object):
    """
    Class for processing evergreen history objects.
    """
    def __init__(self, jsonobj):
        self._raw = sorted(jsonobj, key=lambda d: d["order"])
        self._noise = None

    def testnames(self):
        """Get the set of test names"""
        return set(
            list(
                itertools.chain.from_iterable([[z["name"] for z in c["data"]["results"]]
                                               for c in self._raw])))

    def task(self):
        """Get the task that this history belongs to (as recorded in the history.json file)."""
        return self._raw[0]['task_name']

    def series_at_revision(self, testname, revision):
        """Get history data for specificied revision"""
        test_series = self.series(testname)
        for result in test_series:
            if result["revision"] == revision:
                return result
        return None

    def series_at_tag(self, testname, tag_name):
        """Get the history data for a tagged result"""
        test_series = self.series(testname)
        for result in test_series:
            if result["tag"] == tag_name:
                return result
        return None

    def series_at_n_before(self, testname, revision, number):
        """
            Returns the 'n' items in the series under the given test name that
            appear prior to the specified revision.
        """
        results = []
        older_build = 0
        test_series = self.series(testname)
        for result in test_series:
            if result["revision"] == revision:
                break
            older_build += 1
            results.append(result)

        if older_build > number:
            return results[-1 * number:][0]
        return None

    def series_at_n_days_before(self, testname, revision, number):
        """
            Returns the items in the series under the given test name that
            appear 'n' days prior to the specified revision.
        """
        results = {}
        # Date for this revision
        test_series = self.series_at_revision(testname, revision)
        if test_series == []:
            return []
        refdate = parser.parse(test_series["create_time"]) - timedelta(days=number)

        test_series = self.series(testname)
        for result in test_series:
            if parser.parse(result["create_time"]) < refdate:
                # Make sure the result is the newest one older than the threshold
                if not results or results["create_time"] < result["create_time"]:
                    results = result
        return results

    def series(self, testname):
        """
        Returns the items in the series under the given test name
        """
        for commit in self._raw:
            # get a copy of the samples for those whose name matches the given testname
            matching = [
                results for results in commit["data"]["results"] if results["name"] == testname
            ]
            if matching:
                result = matching[0]
                result["revision"] = commit["revision"]
                result["tag"] = commit["tag"]
                result["order"] = commit["order"]
                result["create_time"] = commit["create_time"]
                result["max"] = max(f["ops_per_sec"] for f in result["results"].values()
                                    if isinstance(f, dict))
                result["threads"] = [
                    f for f in result["results"] if isinstance(result["results"][f], dict)
                ]
                yield result

    def compute_noise_levels(self):
        """
        For each test, go through all results, and compute the average
        noise (max - min) for the series

        """
        self._noise = {}
        testnames = self.testnames()
        for test in testnames:
            self._noise[test] = {}
            test_series = self.series(test)
            threads = []
            for result in test_series:
                threads = result["threads"]
                break

            # Determine levels from last commit? Probably a better way to do this.
            for thread in threads:
                test_series = self.series(test)
                self._noise[test][thread] = sum(
                    (compute_range(x["results"][thread].get("ops_per_sec_values", [0]))[2]
                     for x in test_series if thread in x["results"]))
                test_series = self.series(test)
                self._noise[test][thread] /= sum(1 for x in test_series if thread in x["results"])

    def noise_levels(self, testname):
        """
        Returns the average noise level of the given test. Noise levels
        are thread specific. Returns an array

        """
        # check if noise has been computed. Compute if it hasn't
        if not self._noise:
            print("Computing noise levels")
            self.compute_noise_levels()
        # Look up noise value for test
        if testname not in self._noise:
            print("Test %s not in self._noise" % (testname))
        return self._noise[testname]


# We wouldn't need this function if we had numpy installed on the system
def compute_range(result_list):
    '''
       Compute the max, min, and range (max - min) for the result list
    '''
    minimum = maximum = result_list[0]
    for result in result_list:
        if result < minimum:
            minimum = result
        if result > maximum:
            maximum = result
    return (maximum, minimum, maximum - minimum)
