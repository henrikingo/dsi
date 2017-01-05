#!/usr/bin/env python2.7

""" Script to stage and run baselines for mongo-perf """

import argparse
import copy
from itertools import chain
import logging
import os
import os.path
import re
import subprocess
import sys
import yaml


LOGGER = logging.getLogger(__name__)


class UnsupportedBaselineError(Exception):
    '''
    Exception for when we don't know about a particular baseline
    '''
    pass


def patch_perf_yaml_strings(perfyaml, version_link, shell_link):
    '''
    Generates a perf.yml file for the baseline run.

    :param dict perfyaml: The current existing perf.yml to update
    :param str version_link: The end of the URL for the mognod
    :param str shell_link: The end of the URL for the mongo shell to use
    :rtype dict: The updated configuration file
    '''
    outyaml = copy.deepcopy(perfyaml)  # Don't change the input dictionary

    # Update download links
    outyaml['functions']['start server'][1]['params']['remote_file'] = version_link
    outyaml['functions']['start server'][2]['params']['remote_file'] = shell_link

    # Remove the depenencies on compile
    for task in outyaml['tasks']:
        if 'depends_on' in task:
            task['depends_on'] = [dependency for dependency in task['depends_on']
                                  if dependency['name'] != "compile"]
            if len(task['depends_on']) == 0:  # Nothing left after removing compile dependency
                task.pop('depends_on')

    return outyaml


def get_base_version(version):
    '''
    Given a version string, return the first two places.

    Ex: '3.2.1' --> '3.2'

    :param str version: The version string
    '''

    return '.'.join(version.split('.')[0:2])


class BaselineUpdater(object):
    '''
    Class to handle setting up and running new baseline runs
    '''

    def __init__(self):
        ''' init '''
        source_dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(source_dir, 'baseline_config.yml')) as config_file:
            self.config = yaml.load(config_file)

    def patch_perf_yaml_mongod_flags(self, perfyaml, version):
        '''Patch the given yaml file to remove any mognod command line flags
        that are inappropriate for the given version.

        :param dict perfyaml: The current existing perf.yml to update
        :param str version: The version string of the mongod to use
        :rtype dict: The updated configuration file
        '''
        mongod_flag_replacements = self.config['mongod_flags']
        outyaml = copy.deepcopy(perfyaml)  # Don't change the input dictionary

        # Get the base version
        base_version = get_base_version(version)

        # Any flags that need to be changed?
        if base_version in mongod_flag_replacements:
            # Find the startup flags and change them
            # In buildvariants, under expansions.
            for variant in outyaml['buildvariants']:
                if 'expansions' in variant and 'mongod_flags' in variant['expansions']:
                    flags = variant['expansions']['mongod_flags']
                    for replacement in mongod_flag_replacements[base_version]:
                        flags = re.sub(replacement['pattern'], replacement['replace'], flags)
                    variant['expansions']['mongod_flags'] = flags
        return outyaml

    def patch_perf_yaml(self, perfyaml, version, project):
        '''
        Generates a perf.yml file for the baseline run.

        :param dict perfyaml: The current existing perf.yml to update
        :param str version: The version string of the mongod to use
        :param str project: The project to run against (.e.g., performance)
        :rtype dict: The updated configuration file
        '''

        mongod_links = self.config['mongod_links']
        shell_link = self.config['mongo_shells'][project]
        if version not in mongod_links:
            raise UnsupportedBaselineError(version)
        perfyaml_updated = self.patch_perf_yaml_mongod_flags(perfyaml, version)
        perfyaml_updated = patch_perf_yaml_strings(perfyaml_updated, mongod_links[version],
                                                   shell_link)
        return perfyaml_updated

    def get_tasks(self, perfyaml, version):
        '''Return a list of strings with the task names for the
        project. Skips tasks explicitly listed in disabled_tasks in
        the config.

        :param dict perfyaml: Input perf.yml file
        :param str version: The version string of the mongod to use
        :rtype list: List of task names

        '''

        # Get tasks to skip if anything.
        base_version = get_base_version(version)
        skip_tasks = self.config['disabled_tasks'].get(base_version, dict())
        return [task['name'] for task in perfyaml['tasks'] if task['name'] not in skip_tasks]

    def prepare_patch_cmd(self, perfyaml, version, project):
        '''
        Construct command line call for evergreen to start the patch.

        :param dict perfyaml: The current existing perf.yml to update
        :param str version: The version string of the mongod to use
        :param str project: The project to run against (.e.g., performance)
        :rtype list: The arguments to popen for evergreen call
        '''

        # Want all variants and all tasks except compile
        variants = format_repeated_args('-v', get_variants(perfyaml))
        tasks = self.get_tasks(perfyaml, version)
        # Don't run the compile task
        tasks.remove('compile')
        tasks = format_repeated_args('-t', tasks)
        LOGGER.debug('Tasks are %s', tasks)

        description = '{0} baseline for project {1}'.format(version, project)
        return ([get_evergreen(), 'patch', '-p', project, '-d', description, '-y', '-f'] +
                variants + tasks)

    def run_patch(self, version, project):
        '''Updated perf.yml and start a patch build. Assumes it is run in the
        mongo/etc directory

        :param str version: The version string of the mongod to use
        :param str project: The project to run against (.e.g., performance)
        '''

        # Read in the existing YAML file
        with open('perf.yml') as perf_file:
            perfyaml = yaml.load(perf_file)

        # Update the yaml file for this patch build.
        with open('perf.yml', 'w') as perf_file:
            yaml.dump(self.patch_perf_yaml(perfyaml, version, project), perf_file)

        cmdline_args = self.prepare_patch_cmd(perfyaml, version, project)
        LOGGER.debug("Calling %s", cmdline_args)
        subprocess.Popen(cmdline_args)


def get_evergreen():
    '''
    Get the path to the evergreen executable
    '''

    # Not sure why this is needed, and Popen doesn't find it in the path
    path = os.environ['PATH']
    for directory in path.split(':'):
        if os.path.exists(os.path.join(os.path.expanduser(directory), 'evergreen')):
            return os.path.join(os.path.expanduser(directory), 'evergreen')


def get_variants(perfyaml):
    '''
    Return a list of strings with the variant names for the project

    :param dict perfyaml: Input perf.yml file
    :rtype list: List of variant names
    '''
    return [variant['name'] for variant in perfyaml['buildvariants']]


def format_repeated_args(flag, arglist):
    '''Format repeated args for calling evergreen.

    Ex. Multiple tasks can be passed in. To run two tasks: taskA,
    taskB, the command line arguments need to look like:
    -t taskA -t taskB

    :param string flag: The flag used per argument
    :param list arglist: List of string arguments
    :rtype list: the list that can be passed to Popen

    '''

    return list(chain.from_iterable([[flag, arg] for arg in arglist]))


def main(argv):
    '''
    Main entrypoint to setup_baselines
    '''

    description = ('Generate baselines for mongo-perf (microbenchmarks). This program should '
                   'be run from the etc directory in your mongo repo. Perf.yml should be up to '
                   'date. If you are baselining in anticipation of pushing a change to perf.yml,'
                   ' those changes should be present when running this script.')

    arg_parser = argparse.ArgumentParser(description=description)
    arg_parser.add_argument('-d',
                            '--debug',
                            action="store_true",
                            help='Turn on debug output')
    arg_parser.add_argument('-p',
                            '--project',
                            help='Project to use when running baselines (e.g., performance)',
                            required=True)
    arg_parser.add_argument('--version',
                            help='Baseline version (e.g., 3.2.10)',
                            required=True)

    args = arg_parser.parse_args(argv)
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    updater = BaselineUpdater()
    updater.run_patch(args.version, args.project)


if __name__ == '__main__':
    main(sys.argv[1:])
