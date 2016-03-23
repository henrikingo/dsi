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

"""Get tagged data for a particular Evergreen task."""

import argparse
import json
import logging
import os
import sys

import evergreen
import helpers


def get_tagged_data(project, variants, tasks, filename_format, cli):
    """Get the raw tagged data for this task.

    :param str project: The project ID in Evergreen (e.g. 'performance', 'sys-perf')
    :param list[str] variants: The names of the build variants to search for tasks
    :param list[str] tasks: The names of the tasks (e.g. 'insert', 'industry_benchmarks_WT')
    :param str filename_format: The format of the filename
    :param evergreen.Client cli: A handle on an Evergreen client
    :rtype: dict
    """
    global logger

    try:
        revision = cli.get_recent_revisions(project)[-1]['revision']
    except IndexError:
        raise ValueError('No data found for project {project}'.format(project=project))
    except KeyError:
        raise RuntimeError('Failed to find any revisions for project {project}'.format(project=project))

    for build_variant, build_variant_id in cli.build_variants_from_git_commit(project, revision):
        if 'comp' in build_variant or not helpers.matches_any(build_variant, variants):
            continue

        for task_name, task_id in cli.tasks_from_build_variant(build_variant_id):
            if 'compile' in task_name or not helpers.matches_any(task_name, tasks):
                continue

            tags = cli.query_mongo_perf_task_tags(task_name, task_id)
            filename = filename_format.format(variant=build_variant, task=task_name)
            with open(filename, 'w') as fp:
                logger.info('Saving tagged data to {filename}'.format(filename=filename))
                json.dump(tags, fp, sort_keys=True, separators=[',', ':'], indent=4)


if __name__ == '__main__':
    global logger
    parser = argparse.ArgumentParser(prog='get-tags',
                                     description='Get tagged task data')
    parser.add_argument('-p',
                        '--project',
                        default='performance',
                        help='The Evergreen project from which to fetch tagged data')
    parser.add_argument('-v',
                        '--variants',
                        default='.*',
                        help='The build variant or variants to get data from; defaults to all')
    parser.add_argument('-t',
                        '--tasks',
                        default='.*',
                        help='The tasks to get tagged data from; defaults to all')
    parser.add_argument('-f',
                        '--format',
                        default='{variant}.{task}.tags.json',
                        help='Format for tag data file names. Wildcards are {variant} and {task}')
    parser.add_argument('-c',
                        '--config',
                        default=os.path.expanduser('~/.evergreen.yml'),
                        help='The path to your .evergreen.yml configuration')
    parser.add_argument('--verbose',
                        action='store_true',
                        help='Enable verbose output')

    # Parse the arguments and initialize the logging output
    args = parser.parse_args()
    logger = logging.getLogger('tags.information')
    logger.addHandler(logging.StreamHandler(sys.stdout))
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # Pass the rest of the command-line arguments
    get_tagged_data(args.project, args.variants, args.tasks, args.format, evergreen.Client(args.config))
