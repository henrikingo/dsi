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

"""Runner script for updating overrides."""

import argparse
import os

import override
import evergreen


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='update-overrides',
                                     description='Update performance test overrides')
    parser.add_argument('revision',
                        help='The Git commit SHA of the revision')
    parser.add_argument('tag',
                        help='The tag to compare against (e.g. "3.1.8-Baseline")')
    parser.add_argument('ticket',
                        help='The JIRA ticket associated with this override update')
    parser.add_argument('-v',
                        '--variants',
                        help='The build variant or list of build variants to update')
    parser.add_argument('-k',
                        '--tasks',
                        help='The task or list of tasks to update')
    parser.add_argument('-t',
                        '--tests',
                        help='The test or list of tests to update')
    parser.add_argument('-f',
                        '--override-file',
                        default='override.json',
                        help='The path to the override file to update')
    parser.add_argument('-d',
                        '--destination-file',
                        default='override.json',
                        help='The path to write the updated override')
    parser.add_argument('-c',
                        '--config',
                        default=os.path.join(os.path.expanduser('~'), '.evergreen.yml'),
                        help='The path to your .evergreen.yml configuration')

    # Parse the arguments and find the override file
    args = parser.parse_args()
    ovr = override.Override(args.override_file)

    # Pass the rest of the command-line arguments
    ovr.update_performance_reference(args.revision,
                                     args.tag,
                                     args.ticket,
                                     evg=evergreen.Client(args.config),
                                     variants=args.variants,
                                     tasks=args.tasks,
                                     tests=args.tests)

    # Dump the new file as JSON
    ovr.save_to_file(args.destination_file)
