#!/bin/env python2.7

import json
import sys
import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--baseline", default="base.json", dest="baseline",
                        help="path to json file containing baseline data")
    parser.add_argument("-c", "--comparison", default="compare.json", dest="compare",
                        help="path to json file containing comparison data")
    args = parser.parse_args()

    compare = json.load(open(args.compare))
    baseline = json.load(open(args.baseline))
    baselinedict = dict((s['name'], s) for s in baseline['results'])

    # Note, we're putting things in an ops_per_sec fields, but it's really
    # a ratio. Would like to rename and have evergreen pick it up.

    newresults = []
    reportresults = []
    fails = []
    for result in compare['results'] :
        nresult = {'name' : result['name']}
        nreport = {'test_file' : result['name'], 'exit_code' : 0, 'elapsed' : 5,
                   'start': 1441227291.962453, 'end': 1441227293.428761}
        r = result['results']
        s = baselinedict[result['name']]['results']
        nresult['results'] =  dict((thread,
                                    {'ops_per_sec' : 100*r[thread]['ops_per_sec']/s[thread]['ops_per_sec']})
                                   for thread in r if type(r[thread]) == type({}) and thread in s)
        newresults.append(nresult)

        out = open("perf.json", 'w')
        json.dump({'results' : newresults}, out, indent=4, separators=(',', ':'))

if __name__ == '__main__':
    main()
