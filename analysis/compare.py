#!/usr/bin/env python2.7
"""Compute the ratio of scores in one test run to those in another."""

import json
import argparse

def main():
    """Script entry point."""
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
    for result in compare['results']:
        nresult = {'name' : result['name']}
        res = result['results']
        baseline_res = baselinedict[result['name']]['results']
        nresult['results'] = dict(
            (thread, {'ops_per_sec' : 100*res[thread]['ops_per_sec'] /
                                      baseline_res[thread]['ops_per_sec']})
            for thread in res if isinstance(res[thread], dict) and thread in baseline_res)
        newresults.append(nresult)

    out = open("perf.json", 'w')
    json.dump({'results' : newresults}, out, indent=4, separators=(',', ':'))

if __name__ == '__main__':
    main()
