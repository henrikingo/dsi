"""Functions for analyzing the throughput-over-time data generated by YCSB."""

import logging
import os
import itertools
import collections

LOGGER = logging.getLogger(__name__)

Throughput = collections.namedtuple("Throughput", ["time", "ops"])

def analyze_ycsb_throughput(reports_dir_path):
    """
    Search `reports_dir_path` for YCSB log files (any file whose name starts with
    "test_screen_capture"), extract their throughput-over-time data, and analyze it for errors like
    periods of significantly decreased throughput. Return a list of test-result dictionaries that
    can be plugged straight into a "report.json" file.
    """

    results = []
    LOGGER.info("Starting YCSB throughput analysis.")
    for num, path in enumerate(_get_ycsb_file_paths(reports_dir_path)):
        LOGGER.info("Reading file: " + path)
        with open(path) as ycsb_file:
            throughputs = _throughputs_from_lines(ycsb_file)
        pass_test, result_message = _analyze_throughputs(throughputs)
        results.append({
            "status": "pass" if pass_test else "fail",
            "log_raw": "File: {0}\n".format(path) + result_message,
            "test_file": "ycsb-throughput-analysis." + str(num),
            "start": 0,
            "exit_code": 0 if pass_test else 1
        })

    return results

def _get_ycsb_file_paths(directory_path):
    """
    Recursively search the directory tree starting at `directory_path` for files whose name starts
    with "test_screen_capture.log" and return a list of their fully qualified paths.
    """

    file_paths = []
    for sub_directory_path, _, filenames in os.walk(directory_path):
        for filename in filenames:
            if filename.startswith("test_screen_capture.log"):
                file_paths.append(os.path.join(sub_directory_path, filename))

    return file_paths

def _throughputs_from_lines(lines):
    """
    Search `lines`, a list of the lines taken from a YCSB log file, for throughput data, and return
    it in the form of a list of `(time, throughput)` tuples, where `throughput` is the ops/sec
    throughput value and `time` is the number of seconds since the start of the test that the
    throughput value was reported at.
    """

    # A sample line from the YCSB file might look like:
    # " 10 sec: 185680 operations; 18543.89 current ops/sec; [INSERT AverageLatency(us)=1692.38]"

    throughputs = []
    for line in lines:
        if not line.startswith(" "):
            continue

        line = line.strip()
        components = line.split(": ", 1)
        if len(components) < 2:
            continue

        timestamp_str, rest = components
        timestamp = float(timestamp_str.split(" ")[0])

        components = rest.split("; ")
        if len(components) < 2:
            continue

        ops_per_sec = float(components[1].split(" ")[0])
        throughputs.append(Throughput(timestamp, ops_per_sec))

    return throughputs

def _analyze_throughputs(throughputs, max_drop=0.5, min_duration=10, skip_initial_seconds=10): # pylint: disable=too-many-locals
    """
    Analyze throughput data for periods of reduced throughput. Any throughput value that is less
    than the average throughput of the entire run multiplied by `max_drop` is considered a "low"
    throughput; any period of successive low throughputs that's greather than or equal to
    `min_duration` (a number of seconds) is considered an error. Note that we may want to ignore the
    first few datapoints because the test is "warming up" and needs a little bit of time before
    hitting its initial maximum throughput; the amount of time to skip at the beginning of the test
    is specified in `skip_initial_seconds` in seconds (so if `skip_initial_seconds=20` the first 20
    seconds worth of datapoints will be skipped). The function returns `(pass, msg)`, where `pass`
    is a boolean indicating whether the analysis passed successfully (ie no errors were detected)
    and `msg` is a human-friendly string summarizing the findings of the analysis.
    """

    err_messages = []

    # Skip datapoints based on `skip_initial_seconds`. `throughputs` is a list of `(time,
    # throughput)` tuples.
    while throughputs and throughputs[0].time <= skip_initial_seconds:
        throughputs = throughputs[1:]

    if not throughputs:
        return True, (
            "Insufficient data to perform throughput analysis (less than {0} seconds of data "
            "was present).")

    avg_throughput = float(sum(pair.ops for pair in throughputs)) / len(throughputs)
    min_acceptable_throughput = avg_throughput * max_drop
    throughputs_iter = iter(throughputs)

    for throughput in throughputs_iter:
        if throughput.ops < min_acceptable_throughput:
            first_low_throughput_time = throughput.time

            # Search until the point where performance numbers return to normal.
            low_throughputs = list(itertools.takewhile(
                lambda throughput: throughput.ops < min_acceptable_throughput, throughputs_iter))

            # If there aren't at least two consecutive low throughputs there aren't enough
            # datapoints to confidently flag a regression, no matter what the reporting interval is.
            if not low_throughputs:
                continue

            last_low_throughput_time = low_throughputs[-1].time
            duration = last_low_throughput_time - first_low_throughput_time
            if duration >= min_duration:
                # We've detected a long-enough period of reduced throughput.

                low_throughputs_str = "\n".join(
                    "    {0} sec: {1} ops/sec".format(time, throughput)
                    for time, throughput in low_throughputs)
                err_msg = (
                    "Detected low throughput for {0} seconds, starting at {1} seconds and ending "
                    "at {2} seconds. The minimum acceptable throughput is {3} ops/sec (the "
                    "average throughput for the test was {4}ops/sec ), and the low "
                    "throughputs were: \n{5}\n").format(
                        duration, first_low_throughput_time, last_low_throughput_time,
                        min_acceptable_throughput, avg_throughput, low_throughputs_str)
                err_messages.append(err_msg)

    passed = not err_messages
    return passed, "No problems detected." if passed else "\n".join(err_messages)
