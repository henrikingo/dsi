#!/usr/bin/env python2.7
''' Process json output from iperf '''

from __future__ import print_function
import json


def main():
    '''Process results'''
    with open('iperf.json') as result_file:
        results = json.load(result_file)

    print(
        ">>> NetworkBandwidth : {0:12.2f} 1".format(results['end']['sum_sent']['bits_per_second']))

if __name__ == '__main__':
    main()
