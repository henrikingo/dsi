#!/usr/bin/env python2.7
'''Process json output from fio and turn it into a result that
mission control can consume.

The result is adjusted to look like the output from workloads.

'''

from __future__ import print_function
import argparse
import json
import re
import sys


# pylint: disable=too-many-arguments
def format_result(prefix, jobname, write_or_read, testname, result, thread_level=1):
    '''
    Format one test result for consumption by mission control
    '''

    if prefix and prefix[-1] != '_':
        prefix = prefix + '_'
    else:
        prefix = ''
    return ">>> {0}{1}_{2}_{3} : {4:12.2f} {5}".format(prefix, jobname, write_or_read, testname,
                                                       result, thread_level)


def process_results_for_mc(prefix=None, filename='fio.json'):
    ''' Open and process the results

    :param str filename: The name of the file to open
    '''
    with open(filename) as input_file:
        fio_output = json.load(input_file)
    output = []
    # Should iterate over the jobs
    for job in fio_output['jobs']:
        for write_or_read in ['write', 'read']:
            if write_or_read in job:
                result = job[write_or_read]
                jobname = job['jobname']
                if result['iops'] > 0:
                    output.append(format_result(prefix, jobname, write_or_read, "iops",
                                                result['iops']))
                    output.append(format_result(prefix, jobname, write_or_read, "clat_mean",
                                                result['clat']['mean']))
                    output.append(format_result(prefix, jobname, write_or_read, "clat_stddev",
                                                result['clat']['stddev']))
    return output


def filter_results(lines):
    ''' Filter the results to a brief list '''
    test_to_print = ['latency_test_(read|write)_clat_mean',
                     'iops_test_(read|write)_iops',
                     'streaming_bandwidth_test_(read|write)_iops']
    regex = '(' + ')|('.join(test_to_print) + ')'
    matcher = re.compile(regex)
    return [line for line in lines if matcher.search(line)]


def main(argv=None):
    ''' Main function '''

    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description=
                                     'Process fio.json for consumption by mission control')
    parser.add_argument('-b', '--brief', action='store_true', default=True,
                        help="Print out brief results. If -l is also set, the last one wins")
    parser.add_argument('-l', '--long', action='store_false', dest='brief',
                        help="Print out all possible results. If -b is also set, the last one wins")
    parser.add_argument('prefix', nargs='?', help='Prefix to prepend to all test results')
    args = parser.parse_args(argv)
    if args.brief:
        print('\n'.join(filter_results(process_results_for_mc(args.prefix))))
    else:
        print('\n'.join(process_results_for_mc(args.prefix)))

if __name__ == '__main__':
    main()
