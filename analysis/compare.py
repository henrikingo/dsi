#!/usr/bin/env python2.7
"""Compute the ratio of scores in one test run to those in another."""

import argparse
import json
import sys
import util


def compare(this_run, baseline_run):
    """
    Compare two test runs and return the comparison data in the form of a test run.

    `this_run` is the test run to compare against the tagged test run in `baseline_run`.
    """

    newresults = []
    baseline_run = dict((s['name'], s) for s in baseline_run['results'])

    for result in this_run['results']:
        nresult = {'name': result['name']}
        res = result['results']
        baseline_res = baseline_run[result['name']]['results']
        nresult['results'] = dict((thread, {
            'ops_per_sec': 100 * res[thread]['ops_per_sec'] / baseline_res[thread]['ops_per_sec']
        }) for thread in res if isinstance(res[thread], dict) and thread in baseline_res)
        newresults.append(nresult)

    return {"results": newresults}


def main(args):
    """Script entry point."""

    parser = argparse.ArgumentParser()
    parser.add_argument("-b",
                        "--baseline",
                        default="base.json",
                        dest="baseline",
                        help="path to json file containing baseline data")
    parser.add_argument("-c",
                        "--comparison",
                        default="compare.json",
                        dest="compare",
                        help="path to json file containing comparison data")
    args = parser.parse_args(args)

    compare_run = util.get_json(args.compare)
    baseline_run = util.get_json(args.baseline)
    newresults = compare(compare_run, baseline_run)
    with open("perf.json", "w") as out:
        json.dump(newresults, out, indent=4, separators=(',', ':'))


if __name__ == "__main__":
    main(sys.argv[1:])
