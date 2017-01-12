#!/usr/bin/env python2.7
'''Process json output from fio and turn it into a result that
mission control can consume.

The result is adjusted to look like the output from workloads.

'''

from __future__ import print_function
import json
import sys

#pylint: disable=too-many-arguments
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

    # Should iterate over the jobs
    for job in fio_output['jobs']:
        for write_or_read in ['write', 'read']:
            if write_or_read in job:
                result = job[write_or_read]
                jobname = job['jobname']
                if result['iops'] > 0:
                    print(format_result(prefix, jobname, write_or_read, "iops", result['iops']))
                    print(format_result(prefix, jobname, write_or_read, "clat_mean",
                                        result['clat']['mean']))
                    print(format_result(prefix, jobname, write_or_read, "clat_stddev",
                                        result['clat']['stddev']))

def main(argv=None):
    ''' Main function '''

    if argv is None:
        argv = sys.argv
    prefix = None
    if len(argv) > 1:
        prefix = argv[1]
    process_results_for_mc(prefix)

if __name__ == '__main__':
    main()
