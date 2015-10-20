# Copyright 2015 MongoDB Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Generates overrides from Evergreen data."""

import argparse
import json
from __future__ import print_function

import perf_regression_check


def generate_overrides(input, output):
    """Generate a new override file.

    Creates a new override file from Evergreen data. The configuration file directs how to generate the overrides. It
    should something like this:

            {
                "variants" : [
                      {
                        "tagfile" : "where.tags.json",
                        "tag" : "3.1.4-Baseline"
                        "tests" : ["Inserts.PartialIndex.NonFilteredRange",
                                   "Inserts.PartialIndex.FullRange",
                                   "Inserts.PartialIndex.FilteredRange"]
                      },
                      {
                        "tagfile" : "update.tags.json",
                        "tag" : "3.1.4-Baseline"
                        "tests" : ["Update.DocValidation.OneInt",
                                   "Update.DocValidation.TenInt",
                                   "Update.DocValidation.TwentyInt"]
                      }
                ]
            }

    :param input: A configuration file specifying the variants and tasks for generating overrides.
    :param output: The destination to which the overrides will be written. Must be writable.
    :returns: None.
    """
    with open(input) as fd:
        config = json.load(fd)

    overrides = {}

    for variant in config['variants']:
        with open(variant['tagfile']) as fd:
            history = perf_regression_check.History(json.load(fd))

            for test in variant['tests']:
                overrides[test] = history.seriesAtTag(test, variant['tag'])

    with open(output) as fd:
        json.dump(overrides, fd, indent=4, separators=(',', ':'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='generate',
                                     description='Generate perf test overrides')
    parser.add_argument('input',
                        help='An input JSON configuration file for setting up overrides')
    parser.add_argument('output',
                        help='The destination for the override file (must be writable)')

    args = parser.parse_args()
    generate_overrides(args.input, args.output)

