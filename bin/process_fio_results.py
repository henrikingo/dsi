#!/usr/bin/env python2.7
'''Process json output from fio and turn it into a result that
mission control can consume.

The result is adjusted to look like the output from workloads.

'''

from __future__ import print_function
import json

def process_results_for_mc(filename='fio.json'):
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
                    print(">>> {0}_{1}_{2} : {3:12.2f} {4}".format(jobname, write_or_read, "iops",
                                                                   result['iops'], 1))
                    print(">>> {0}_{1}_{2} : {3:12.2f} {4}".format(jobname,
                                                                   write_or_read,
                                                                   "clat_mean",
                                                                   result['clat']['mean'],
                                                                   1))
                    print(">>> {0}_{1}_{2} : {3:12.2f} {4}".format(jobname,
                                                                   write_or_read,
                                                                   "clat_stddev",
                                                                   result['clat']['stddev'],
                                                                   1))

if __name__ == '__main__':
    process_results_for_mc()
