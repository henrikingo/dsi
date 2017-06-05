"""
Functions for analyzing `mongod` log files for suspect messages. Useful for sanity checking that
everything ran smoothly during a test.
"""

from __future__ import print_function
import logging
import os
import os.path
import time

import rules
import util

LOGGER = logging.getLogger(__name__)
KEEPALIVE_TIME = time.time()

def analyze_logs(reports_dir_path, perf_file_path=None):
    """
    Analyze all the "mongod.log" logs in the directory tree rooted at `reports_dir_path`,
    and return a list of test-result dictionaries ready to be placed in the report JSON generated
    by `post_run_check`/`perf_regression_check`. If you want to only analyze log messages generated
    during the time of an actual test run, and not test setup/transition, then set `perf_file_path`
    to the path of the performance results file (probably `perf.json`) generated by the test runner
    (benchrun or mission-control), which contains relevant timestamp data.
    """

    LOGGER.info("Analyzing logs")
    results = []
    num_failures = 0

    test_times = None
    if perf_file_path:
        LOGGER.info("Getting test times from `%s`", perf_file_path)
        try:
            test_times = util.get_test_times(perf_file_path)
        except IOError:
            LOGGER.error("Failed to read file `%s`", perf_file_path)

    bad_logs = _get_bad_log_lines(reports_dir_path, test_times)

    for log_num, (log_path, bad_lines) in enumerate(bad_logs):
        result = {
            "status": "fail" if bad_lines else "pass",
            "log_raw": _format_log_raw(log_path, bad_lines),
            "test_file": "mongod.log.{0}".format(log_num),
            "start": 0,
            "exit_code": 1 if bad_lines else 0
        }
        results.append(result)

        if bad_lines:
            num_failures += 1

    return results, num_failures

def _format_log_raw(path, bad_lines):
    """
    Return a nicely formatted `log_raw` message for a log file at path `path` with bad messages
    `bad_lines` (could be empty, indicating a passing test).
    """

    msg_path_header = "\nLog file: {0}\n".format(path)
    msg_body = "No bad messages found" if not bad_lines else \
        "Number of bad lines: {0}\nBad lines below: \n{1}\n{2}".format(
            path, len(bad_lines), "".join(bad_lines))
    return msg_path_header + msg_body

def _get_bad_log_lines(reports_dir_path, test_times=None):
    """
    Recursively search the directory `reports_dir_path` for files called "mongod.log" and identify
    bad messages in each. `test_times` is a list of `(start, end)` `datetime` tuples specifying the
    start and end times of the actual tests that ran, so that we can ignore log messages generated
    during a test setup/transition phase. Return a list of (path, bad_messages) tuples, where `path`
    is the path of the `mongod.log` and `bad_messages` is a list of the bad messages.
    """

    bad_messages_per_log = []
    for path in _get_log_file_paths(reports_dir_path):
        LOGGER.info("Analyzing log file: " + path)
        bad_messages = []
        with open(path) as log_file:
            # Not using list comprehension due to the need to call _print_keepalive_msg()
            for line in log_file:
                if line != "\n" and rules.is_log_line_bad(line, test_times):
                    bad_messages.append(line)
                _print_keepalive_msg(path)
        bad_messages_per_log.append((path, bad_messages))

    return bad_messages_per_log

def _get_log_file_paths(dir_path):
    """
    Recursively search `dir_path` for files called "mongod.log" and return a list of their fully
    qualified paths.
    """

    log_filename = "mongod.log"
    log_paths = []
    for sub_dir_path, _, filenames in os.walk(dir_path):
        if log_filename in filenames:
            log_paths.append(os.path.join(sub_dir_path, log_filename))

    return log_paths

def _print_keepalive_msg(path):
    """Print a log message every 15 minutes to prevent evergreen timeouts

       If we want to use this more broadly, we would make it into its own small utility class,
       parameterize the time interval, add unit tests, and that would also make the use of a
       global variable go away.
    """
    global KEEPALIVE_TIME #pylint: disable=global-statement
    quarter = 60*15
    now = time.time()
    if now > KEEPALIVE_TIME + quarter:
        KEEPALIVE_TIME += quarter
        LOGGER.info("Still analyzing %s...", path)
