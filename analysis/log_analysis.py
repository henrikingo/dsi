"""
Functions for analyzing `mongod` log files for suspect messages. Useful for sanity checking that
everything ran smoothly during a test.
"""

from __future__ import print_function
import os
import logging

LOGGER = logging.getLogger(__name__)

def analyze_logs(reports_dir_path):
    """
    Analyze all the "mongod.log" logs in the directory tree rooted at `reports_dir_path`, and return
    a list of test-result dictionaries ready to be placed in the report JSON generated by
    `post_run_check`/`perf_regression_check`.
    """

    results = []
    num_failures = 0
    bad_logs = _get_bad_log_lines(reports_dir_path)

    for log_num, (log_path, bad_lines) in enumerate(bad_logs):
        result = {
            "status": "fail" if bad_lines else "pass",
            "log_raw": _format_bad_lines_err_msg(log_path, bad_lines) if bad_lines \
                else "No bad log messages found.",
            "test_file": "mongod.log.{0}".format(log_num),
            "start": 0,
            "exit_code": 1 if bad_lines else 0
        }
        results.append(result)

        if bad_lines:
            num_failures += 1

    return results, num_failures

def _format_bad_lines_err_msg(path, bad_lines):
    """
    Return a nicely formatted error message for a log file at path `path` with bad messages
    `bad_lines`.
    """

    return "\nLog file: {}\nNumber of bad lines: {}\nBad lines below: \n{}\n".format(
        path, len(bad_lines), "".join(bad_lines))

def _get_bad_log_lines(reports_dir_path):
    """
    Recursively search the directory `reports_dir_path` for files called "mongod.log" and identify
    bad messages in each. Return a list of (path, bad_messages) tuples, where `path` is the path of
    the `mongod.log` and `bad_messages` is a list of the bad messages.
    """

    bad_messages_per_log = []
    for path in _get_log_file_paths(reports_dir_path):
        LOGGER.info("Analyzing log file: " + path)
        with open(path) as log_file:
            bad_messages = [line for line in log_file if line != "\n" and _is_log_line_bad(line)]
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

# TODO: break out the following into a config file
# https://jira.mongodb.org/browse/PERF-603

BAD_LOG_TYPES = ["F", "E"] # See https://docs.mongodb.com/manual/reference/log-messages/
BAD_MESSAGES = [msg.lower() for msg in [
    "starting an election", "election succeeded", "transition to primary"]]

def _is_log_line_bad(log_line):
    """
    Return whether or not `log_line`, a line from a log file, is suspect (see `BAD_LOG_TYPES` and
    `BAD_MESSAGES`).
    """

    _, err_type_char, _, log_msg = log_line.split(" ", 3)
    log_msg = log_msg.lower()
    return err_type_char in ["F", "E"] or any(bad_msg in log_msg for bad_msg in BAD_MESSAGES)