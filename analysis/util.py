# Copyright 2016 MongoDB Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Module of utility functions for analysis"""

from __future__ import absolute_import
from __future__ import division
import doctest
import json
import sys #pylint: disable=wrong-import-order

from evergreen.history import History

def get_json(filename):
    """ Load a file and parse it as json """
    return json.load(open(filename, 'r'))

def read_histories(variant, hfile, tfile, ofile):
    ''' Set up result histories from various files and returns the
    tuple (history, tag_history, overrides):
     history - this series include the run to be checked, and previous or NDays
     tag_history - this is the series that holds the tag build as comparison target
     overrides - this series has the override data to avoid false alarm or fatigues
    '''

    tag_history = None
    history = History(get_json(hfile))
    if tfile:
        tag_history = History(get_json(tfile))
    # Default empty override structure
    overrides = {'ndays': {}, 'reference': {}, 'threshold': {}}
    if ofile:
        # Read the overrides file
        foverrides = get_json(ofile)
        # Is this variant in the overrides file?
        if variant in foverrides:
            overrides = foverrides[variant]
    return(history, tag_history, overrides)

def compare_one_result_base(current, reference, noise_level=0,
                            noise_multiple=1, default_threshold=0.05):
    '''Compare one result.

    Returns a tuple: a boolean indicating if the test passed or
    failed, the percent difference from the target, and the percent
    threshold used.

    keyword arguments:
    current -- The throughput achieved by the current run
    reference -- The reference performance for this rule and test
    noise_level -- The noise level of the reference data
    noise_multiple -- The multiplier to use with the noise data
    default_threshold -- The minimum percentage allowed regression

    >>> compare_one_result_base(1, 0)
    (False, 0, 0)
    >>> compare_one_result_base(1, 1)
    (False, 0.0, 0.05)
    >>> compare_one_result_base(1, 2)
    (True, -0.5, 0.05)
    >>> compare_one_result_base(1, 3)
    (True, -0.6666666666666666, 0.05000000000000001)

    >>> compare_one_result_base(10, 11, default_threshold=0.08)
    (True, -0.09090909090909091, 0.08)
    >>> compare_one_result_base(10, 11, default_threshold=0.10)
    (False, -0.09090909090909091, 0.1)

    >>> compare_one_result_base(10, 11, noise_level=1.2)
    (False, -0.09090909090909091, 0.10909090909090909)
    >>> compare_one_result_base(10, 11, noise_level=0.9)
    (True, -0.09090909090909091, 0.08181818181818182)

    '''
    failed = False
    noise = noise_level * noise_multiple
    delta = default_threshold * reference
    if delta < noise:
        delta = noise
    # Do the check
    if reference - current > delta:
        failed = True

    if reference == 0:
        percent_delta = percent_threshold = 0
    else:
        percent_delta = (current - reference)/reference
        percent_threshold = delta/reference
    return (failed, percent_delta, percent_threshold)

def log_header(testname):
    ''' Create the string for the log message header

    >>> print log_header("test")
    Test: test
       Rule   |  State   |  Compared_to  |Thread |  Target   | Achieved  | delta(%)  |threshold(%)
    ----------+----------+---------------+-------+-----------+-----------+-----------+------------
    <BLANKLINE>

    '''

    log = "Test: " + testname + "\n"
    log += '{0:^10}|{1:^10}|{2:^15}|{3:^7}|{4:^11}|{5:^11s}|{6:^11s}|{7:^11s}\n'.format(
        "Rule", "State", "Compared_to", "Thread", "Target",
        "Achieved", "delta(%)", "threshold(%)")
    log += "-"*10 + "+"
    log += "-"*10 + "+"
    log += "-"*15 + "+"
    log += "-"*7 + "+"
    log += "-"*11 + "+"
    log += "-"*11 + "+"
    log += "-"*11 + "+"
    log += "-"*12 + "\n"
    return log



def compare_one_result_values(current, reference, label="Baseline",
                              thread_level="max", noise_level=0,
                              noise_multiple=1, default_threshold=0.05,
                              using_override=None, compared_to="Missing"):
    #pylint: disable=too-many-arguments,too-many-locals,line-too-long
    '''Compare one result and create log message.

    Returns a pair: a boolean indicating if the test passed or failed,
    and a string with the log message

    keyword arguments:
    current -- The throughput achieved by the current run
    reference -- The reference performance for this rule and test
    label -- String rule name (e.g., BaselineCompare)
    thread_level -- The thread level
    noise_level -- The noise level of the reference data
    noise_multiple -- The multiplier to use with the noise data
    default_threshold -- The minimum percentage allowed regression
    using_override -- Did this comparison use an override. Array of
    strings of type of overrides used
    compared_to -- string. Either a short githash or a tagged baseline used for compare

    >>> compare_one_result_values(1,1)
    (False, ' Baseline |  Passed  |    Missing    |  max  |       1.00|       1.00|      0.00%|      5.00%|')
    >>> compare_one_result_values(1,2)
    (True, ' Baseline |  Failed  |    Missing    |  max  |       2.00|       1.00|    -50.00%|      5.00%|')
    >>> compare_one_result_values(1,2,"Previous", 3, 1.2, 1)
    (False, ' Previous |  Passed  |    Missing    |   3   |       2.00|       1.00|    -50.00%|n    60.00%|')
    >>> compare_one_result_values(1,2,"Previous", 3, 1.2, 1, using_override=["reference"], compared_to="Githash")
    (False, ' Previous |  Passed  |*   Githash    |   3   |       2.00|       1.00|    -50.00%|n    60.00%|')
    >>> compare_one_result_values(1,2,"Previous", 3, 1.2, 1, using_override=["reference"], compared_to="Githash")
    (False, ' Previous |  Passed  |*   Githash    |   3   |       2.00|       1.00|    -50.00%|n    60.00%|')
    >>> compare_one_result_values(1,2,"Previous", 3, 0.1, using_override=["threshold", "reference"])
    (True, ' Previous |  Failed  |*   Missing    |   3   |       2.00|       1.00|    -50.00%|t     5.00%|')

    '''
    #pylint: enable=line-too-long
    (failed, percent_delta, percent_threshold) = \
        compare_one_result_base(current, reference, noise_level,
                                noise_multiple, default_threshold)

    if failed:
        pass_fail = "Failed"
    else:
        pass_fail = "Passed"

    target_from_override = " "
    threshold_from_override = " "
    # Check for override conditions.
    # 1. Is target/reference from an override
    if using_override and "reference" in using_override:
        target_from_override = "*"
    # 2. Is the precent_threshold from an override?
    if using_override and "threshold" in using_override:
        threshold_from_override = "t"
    # 3. Is the percent_threshold from the noise?
    # Yes, the floating point comparison gives the wrong answer on
    # occassion if I don't add the small number to the equality
    # comparison
    if percent_threshold > default_threshold + 0.00001:
        threshold_from_override = "n"

    log = "{0:^10}|{1:^10}|{2}{3:^14}|{4:^7}|{5:>11.2f}|{6:>11.2f}|{7:>11.2%}|{8}{9:>10.2%}|"
    log = log.format(label, pass_fail, target_from_override,
                     compared_to, thread_level, reference, current,
                     percent_delta, threshold_from_override,
                     percent_threshold)
    return (failed, log)

def compare_one_result(this_one, reference, label, thread_level="max",
                       noise_level=0, noise_multiple=1,
                       default_threshold=0.05, using_override=False):
    #pylint: disable=too-many-arguments
    '''Compare one result and create log message.

    this_one -- The test result object
    reference -- The reference performance for this rule and test
    label -- String rule name (e.g., BaselineCompare)
    thread_level -- The thread level
    noise_level -- The noise level of the reference data
    noise_multiple -- The multiplier to use with the noise data
    default_threshold -- The minimum percentage allowed regression
    using_override -- Did this comparison use an override

    Returns a pair: a boolean indicating if the test passed or failed,
    and a string with the log message
    '''

    if not reference:
        return (True, "No reference data for " + label)

    ref = ""
    current = ""

    if thread_level == "max":
        ref = reference["max"]
        current = this_one["max"]
    else:
        # Don't do a comparison if the thread data is missing
        if thread_level not in reference["results"].keys():
            return (True, "Thread data is missing")
        ref = reference["results"][thread_level]['ops_per_sec']
        current = this_one["results"][thread_level]['ops_per_sec']

    compared_to = ""
    if "tag" in reference and reference["tag"] != "":
        compared_to = reference["tag"]
    else:
        compared_to = reference["revision"][:7] # Use 7 digit SHA hash

    return(compare_one_result_values(current, ref, label,
                                     thread_level, noise_level,
                                     noise_multiple, default_threshold,
                                     using_override, compared_to))


def read_threshold_overrides(test_name, base_threshold, base_thread_threshold, overrides):
    '''
    Read in the overrides file and return thresholds to use for a given test.

    :param str test_name: The name of the current test
    :param float base_threshold: The threshold to use if there is no override
    :param float base_thread_threshold: The per thread threshold to use if there is no override
    :param dict overides: The overrides data structure

    >>> read_threshold_overrides("test", 0.1, 0.15, {})
    (0.1, 0.15, False)
    >>> read_threshold_overrides("test", 0.1, 0.15, {'threshold': {"test" : {"threshold": 0.5,
    ... "thread_threshold": 0.7}}})
    (0.5, 0.7, True)
    '''

    threshold = base_threshold
    thread_threshold = base_thread_threshold
    threshold_override = False

    if 'threshold' in overrides and test_name in overrides['threshold']:
        try:
            threshold = overrides['threshold'][test_name]['threshold']
            thread_threshold = overrides['threshold'][test_name]['thread_threshold']
            threshold_override = True
        except KeyError as exception:
            print >> sys.stderr, "Threshold overrides not properly"\
                "defined. Key {0} doesn't exist for test"\
                "{1}".format(str(exception), test_name)

    return(threshold, thread_threshold, threshold_override)


if __name__ == "__main__":
    doctest.testmod()
