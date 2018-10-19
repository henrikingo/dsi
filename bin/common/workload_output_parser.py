"""
Parser classes for parsing test output into a perf.json file. One parser for each 'type:'.

See SUPPORTED_TYPES below for a list of types you can use.
"""

import csv
import json
import logging
import os
import re

from nose.tools import nottest

LOG = logging.getLogger(__name__)

SUPPORTED_TYPES = {'shell', 'mongoshell', 'ycsb', 'fio', 'iperf', 'linkbench', 'tpcc', 'genny'}


@nottest
def parse_test_results(test, config, timer):
    """
    Based on test['type'], instantiate the correct parser and parse test output into perf.json.

    :param ConfigDict test: The test that just finished running
    :param ConfigDict config: The entire ConfigDict
    :param dict(time) timer: A dict with the start and end times of the test being reported
    :returns: bool True on success else False
    """
    # We want to catch and log all exceptions here, so that we don't raise
    # any exceptions to test_control.py
    parser = parser_factory(test, config, timer)

    return parser.parse_and_save()


def parser_factory(test, config, timer):
    """
    Instantiate a ResultParser instance, based on test['type'].

    :param ConfigDict test: The test that just finished running
    :param ConfigDict config: The entire ConfigDict
    :param dict(time) timer: A dict with the start and end times of the test being reported
    """
    # map test['type'] to a ResultParser class
    parsers = {
        'mongoshell': MongoShellParser,
        # Backward compatibility until mission-control is removed
        'shell': MongoShellParser,
        'ycsb': YcsbParser,
        'fio': FioParser,
        'iperf': IperfParser,
        'linkbench': LinkbenchResultParser,
        'tpcc': TPCCResultParser,
        'genny': GennyResultsParser,
    }
    if test['type'] not in parsers:
        raise ValueError("parser_factory: Unsupported test type: {}".format(test['type']))
    ResultParserChild = parsers[test['type']]  # pylint: disable=invalid-name
    return ResultParserChild(test, config, timer)


def validate_config(config):
    """
    Validate that the given config only includes test types that are supported by a parser.

    The motivation for this method is that result parsing happens at the end of a test, when time
    and money was already spent running the test. If a parser is not found to process the test
    result, they will not be recorded to Evergreen and a user will have to manually search for them
    from the log file. (It's also possible nobody will notice some results are missing. To fail
    early, test_control.py can call this method up front, to validate that all test types are
    supported.

    :param ConfigDict config: A full ConfigDict
    """
    for test in config['test_control']['run']:
        if not test['type'] in SUPPORTED_TYPES:
            raise NotImplementedError("No parser exists for test type {}".format(test['type']))


class Results(object):
    """Holds a list of result objects"""

    def __init__(self, path, storage_engine):
        self.path = path
        self.storage_engine = storage_engine
        self.results = []
        LOG.debug("Trying to read %s", self.path)
        if os.path.isfile(path):
            with open(path) as file_handle:
                self.results = json.load(file_handle)['results']

    # pylint: disable=too-many-arguments
    def add_result(self, test_type, start, end, name, result, threads="1"):
        """
        Merge new result into (potentially) existing perf_json structure.

        There are 3 scenarios:
        1. If the same name+threads exists, we need to find it and add the result to
           ops_per_sec_values list, then recompute ops_per_sec as an average of that.
        2. If the same name exists, but doesn't have this thread level, then add this thread level
        3. If same name+threads doesn't yet exist, we append the new entry to the end of the list.

        :param test_type: aka "workload name"
        :param start: workload timer start
        :param end: workload timer end
        :param str name: Unique name for this test result. (1 test can produce more than 1 result.)
        :param float result: The ops/sec result. (Note, sometimes we actually report latency or
                             duration. In such cases use negative values to preserve "higher is
                             better" semantics.
        :param str threads": The number of client threads the test (name) was run with. Note that
                             this is used as a json key, and therefore must be a string. The
                             combination name+threads defines a unique result in the sense that if
                             there is more than one occurrence, the ops_per_sec field will contain
                             the average of them.
        """
        assert isinstance(name, basestring)
        assert isinstance(threads, basestring)

        existing_entry = self._find_existing_result(name)
        if existing_entry:
            if threads in existing_entry['results']:
                existing_entry['results'][threads]["ops_per_sec_values"].append(result)
                values = existing_entry['results'][threads]["ops_per_sec_values"]
                existing_entry['results'][threads]["ops_per_sec"] = sum(values) / float(len(values))
            else:
                new_thread = {"ops_per_sec": result, "ops_per_sec_values": [result]}
                existing_entry['results'][threads] = new_thread
        else:
            new_entry = {
                "workload": test_type,
                "name": name,
                "start": start,
                "end": end,
                "results": {
                    threads: {
                        "ops_per_sec": result,
                        "ops_per_sec_values": [result]
                    }
                }
            } # yapf: disable
            self.results.append(new_entry)

    def _find_existing_result(self, name):
        """
        Linear scan over self.perf_json to find name.

        :param str name: The test result to find
        """
        for entry in self.results:
            if entry['name'] == name:
                return entry

    def save(self):
        """Save perf.json into self.perf_json_path"""

        # In DSI we output perf.json with a structure of { results: [], storageEngine: '...' }
        # Evergreen populates this with more top level meta data, so that when returned by
        # the Evergreen API, it also includes revision, task_id, variant, timestamps, etc.
        to_serialize = {'results': self.results, 'storageEngine': self.storage_engine}
        with open(self.path, "w") as file_handle:
            json.dump(to_serialize, file_handle, indent=4, separators=[',', ':'], sort_keys=True)


class ResultParser(object):
    """Parent class for all parser types"""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, test, config, timer):
        """
        Set common attributes

        :param ConfigDict test: The test that just finished running
        :param ConfigDict config: The entire ConfigDict
        :param dict(time) timer: A dict with the start and end times of the test being reported
        """
        self.config = config
        self.test_id = test['id']
        self.test_type = test['type']
        self.task_name = config['test_control']['task_name']
        self.reports_root = config['test_control']['reports_dir_basename']
        self.results = Results(config['test_control']['perf_json']['path'],
                               config['mongodb_setup']['mongod_config_file']['storage']['engine'])
        self.timer = timer
        self.input_log = None

    def load_input_log(self):
        """Load self.input_log and return it"""
        if self.input_log is None:
            raise NotImplementedError("self.input_log must be specified by child class.")

        LOG.debug("Trying to read %s", self.input_log)
        with open(self.input_log) as file_handle:
            for line in file_handle:
                yield line

    def parse_and_save(self):
        """Parse self.input_log and merge it into self.perf_json.

        :return: bool True on success else False
        """
        passed = self.parse()
        self.results.save()
        return passed

    def add_result(self, name, result, threads="1"):
        """
        For parameters/returns, see :method: `Results.add_result`
        """
        self.results.add_result(self.test_type, self.timer['start'], self.timer['end'], name,
                                result, threads)

    def parse(self):
        """
        Common code to call _parse and handle errors and sanity checking. The sub class needs to
        implement _parse.

        :return: bool True on success else False
        """
        try:
            self._parse()
        except:  # pylint: disable=bare-except
            LOG.error(
                "ResultParser.parse() encountered an error. At least some results are likely "
                "missing. I will now print the error and then try to gracefully continue to "
                "the end.",
                exc_info=1)
            return False

        return True

    def _parse(self):
        """ The actual test_type specific parser.

        To be implemented by child class. Child class should read its own input from wherever,
        then call `self.add_result(name, result, threads)` for each result.
        """
        raise NotImplementedError()


class InvalidConfigurationException(ValueError):
    """We have bad configuration for the parser."""
    pass


class GennyResultsParser(ResultParser):
    """
    Genny's output doesn't require a parser so this just merges
    genny's output to the configured perf.json path.
    """

    def __init__(self, test, config, timer):
        """
        :param ConfigDict test test-level config
        :param ConfigDict config top-level
        :param timer used by ResultParser
        """
        super(GennyResultsParser, self).__init__(test, config, timer)

        reports_root = config['test_control']['reports_dir_basename']
        input_dir = os.path.join(reports_root, test['id'])

        output_files = test.get('output_files')
        if not output_files:
            raise InvalidConfigurationException(
                'Need single output_files entry. Got {}'.format(output_files))
        if output_files and len(output_files) > 1:
            LOG.info("Got files %s but will only report on first one", output_files)

        self.genny_results_path = os.path.join(input_dir, output_files[0])

    def _parse(self):
        with open(self.genny_results_path) as file_handle:
            for result in json.load(file_handle)['results']:
                self.add_result(self.test_id + '.' + result['name'],
                                result['results'].values()[0]['ops_per_sec'])


class TPCCResultParser(ResultParser):
    """A ResultParser of TPC-C tests"""

    def __init__(self, test, config, timer):
        """Set tpcc specific attributes"""
        super(TPCCResultParser, self).__init__(test, config, timer)
        input_file = config['test_control']['output_file']['tpcc']
        self.input_log = os.path.join(self.reports_root, test['id'], input_file)
        self.threads = None  # We postpone this to _parse()

    def _parse(self):
        """ This parsing logic expects to find "Final Results" line, then the "Thread" count,
        and finally the ops/sec for new orders
        """
        final_results_section_found = False
        for line in self.load_input_log():
            if "Final Results" in line:
                final_results_section_found = True
            if final_results_section_found and "Threads:" in line:
                threads = line.strip().split(" ")[-1]
            if final_results_section_found and "  NEW_ORDER       " in line:
                parts = ' '.join(line.split()).split(" ")
                throughput = float(parts[3]) * int(threads)
                self.add_result(self.test_id, throughput, threads)


class LinkbenchResultParser(ResultParser):
    """
    A ResultParser for linkbench csv files.
    """

    def __init__(self, test, config, timer):
        """Set linkbench specific attributes"""
        super(LinkbenchResultParser, self).__init__(test, config, timer)
        self.input_dir = os.path.join(self.reports_root, test['id'])

        output_files = test.get('output_files')
        if not output_files:
            raise InvalidConfigurationException(
                'Need single output_files entry. Got {}'.format(output_files))
        if output_files and len(output_files) > 1:
            LOG.info("Got csv files %s but will only report on first one", output_files)

        self.input_log = os.path.join(self.input_dir, output_files[0])

    def _parse(self):
        """Read csv file and emit results for the line's [op,mean] values"""
        reader = csv.DictReader(self.load_input_log())
        for row in reader:
            operation = row['op']
            operation_type = 'load' if operation.startswith('LOAD_') else 'request'
            mean = float(row['mean'])
            if mean <= 0:
                LOG.warn("Non-positive mean value reported for row %s", row)
                continue

            inverse = float(1000) / mean
            # linkbench reports non-LOAD values as mean request time (ms/rq)
            # and we want rq/second.
            result = mean if operation_type == 'load' else inverse

            self.add_result(row['op'], result, str(row['threads']))


class MongoShellParser(ResultParser):
    """A ResultParser of mongoshell tests"""

    def __init__(self, test, config, timer):
        """Set mongoshell specific attributes"""
        super(MongoShellParser, self).__init__(test, config, timer)
        input_file = config['test_control']['output_file']['mongoshell']
        self.input_log = os.path.join(self.reports_root, test['id'], input_file)

    def _parse(self):
        """
        Parse mongoshell (benchrun) results as we report them in the workloads repo.

        Example line:
        ">>> contended_update : 18154.473077825252 64"
        """
        for line in self.load_input_log():
            # This is the magic marker for results emitted by mongoshell kind of test
            if not line.startswith(">>> "):
                continue

            parts = line.rstrip().split(" ")
            name = str(parts[1])
            result = float(parts[3])
            threads = str(parts[4])  # Unfortunately in perf.json the threads value is a string
            self.add_result(name, result, threads)


class YcsbParser(ResultParser):
    """A ResultParser of ycsb tests (aka industry benchmarks)"""

    def __init__(self, test, config, timer):
        """Set ycsb specific attributes"""
        super(YcsbParser, self).__init__(test, config, timer)
        input_file = config['test_control']['output_file']['ycsb']
        self.input_log = os.path.join(self.reports_root, test['id'], input_file)
        self.threads = None  # We postpone this to _parse()

    def _parse(self):
        """
        Parse ycsb results

        Example line:
        Command line: -db com.yahoo.ycsb.db.MongoDbClient -s
            -P workloads/workloadEvergreen_50read50update -threads 64 -t
        [OVERALL], Throughput(ops/sec), 47494.99521487923
        """
        for line in self.load_input_log():
            if line.startswith("Command line:"):
                # TODO: We currently set ycsb thread level as a command line option. One could also
                # set it in the ycsb config file. In that case, we would have to grab that from
                # the test object in __init__(). As we don't do that currently, this is not
                # implemented.
                parts = line.rstrip().split(" ")
                for index, part in enumerate(parts):
                    if part == "-threads":
                        self.threads = str(parts[index + 1])  # In perf.json threads is a string
                continue

            # YCSB produces lots of stats, we're only looking for this single line
            if line.startswith("[OVERALL], Throughput(ops/sec), "):
                parts = line.rstrip().split(", ")
                result = float(parts[2])
                name = self.test_id
                self.add_result(name, result, self.threads)

            # if line.startswith("[READ], 95thPercentileLatency(ms), "):
            #     parts = line.rstrip().split(", ")
            #     result = -float(parts[2])
            #     name = self.test_id + "_95th_read_latency_ms"
            #     self.add_result(name, result, self.threads)


class FioParser(ResultParser):
    """A ResultParser of fio results in fio.json"""

    def __init__(self, test, config, timer):
        """Set fio specific attributes"""
        super(FioParser, self).__init__(test, config, timer)
        input_file = config['test_control']['output_file']['fio']
        self.input_log = os.path.join(self.reports_root, test['id'], input_file)
        self.prefix = "fio"

    def load_input_log(self):
        """Override super() to return a huge string instead of list of lines"""
        return "".join(super(FioParser, self).load_input_log())

    def add_filtered_result(self, name, result, threads="1"):
        """
        Filter and merge new result into (potentially) existing perf_json structure

        For fio we filter out a number of tests. The filtering happens here.
        See ResultParser.add_result for parameter values.
        """
        # Regex to filter the results
        test_to_print = [
            'latency_test_(read|write)_clat_mean', 'iops_test_(read|write)_iops',
            'streaming_bandwidth_test_(read|write)_iops'
        ]
        regex = '(' + ')|('.join(test_to_print) + ')'
        matcher = re.compile(regex)
        if matcher.search(name):
            return self.add_result(name, result, threads)

    def _parse(self):
        """Parse fio.json"""
        fio_output = json.loads(self.load_input_log())

        # Iterate over the fio jobs
        for job in fio_output['jobs']:
            for write_or_read in ['write', 'read']:
                if write_or_read in job:
                    result = job[write_or_read]
                    jobname = job['jobname']
                    if result['iops'] > 0:
                        name = self._format_name(jobname, write_or_read, "iops")
                        self.add_filtered_result(name, result['iops'])

                        name = self._format_name(jobname, write_or_read, "clat_mean")
                        self.add_filtered_result(name, result['clat']['mean'])

                        name = self._format_name(jobname, write_or_read, "clat_stddev")
                        self.add_filtered_result(name, result['clat']['stddev'])

    def _format_name(self, jobname, write_or_read, testname):
        return "{0}_{1}_{2}_{3}".format(self.prefix, jobname, write_or_read, testname)


class IperfParser(ResultParser):
    """A ResultParser of iperf3 results in iperf.json"""

    def __init__(self, test, config, timer):
        """Set fio specific attributes"""
        super(IperfParser, self).__init__(test, config, timer)
        input_file = config['test_control']['output_file']['iperf']
        self.input_log = os.path.join(self.reports_root, test['id'], input_file)

    def load_input_log(self):
        """Override super() to return a huge string instead of list of lines"""
        return "".join(super(IperfParser, self).load_input_log())

    def _parse(self):
        """Parse iperf.json"""
        iperf_output = json.loads(self.load_input_log())
        result = iperf_output['end']['sum_sent']['bits_per_second']
        self.add_result("NetworkBandwidth", result)
