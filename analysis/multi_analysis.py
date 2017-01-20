#!/usr/bin/env python2.7
"""
Fetch, analyze and visualize results from builds created with multi_patch_builds.py.

Note, while this takes as input the serialized file (with --continue), it will not
write back to that file. This script only prints out a csv file (or optionally writes to file).
"""

from __future__ import print_function

import argparse
import json
import os
import sys

import matplotlib.pyplot as pyplot
import numpy
import yaml


from evergreen import evergreen_client

class OptionError(Exception):
    """Exception raised for erroneous command line options."""
    pass

class MultiEvergreenAnalysis(object):
    #pylint: disable=too-many-instance-attributes
    """
    Fetch, analyze and visualize results from builds created with MultiEvergreen.
    """

    def __init__(self, cli_args=None):
        """Constructor."""
        self.cli_args = cli_args
        # Instance of argparse
        self.parser = None
        # Default config options
        self.config = {
            'evergreen_config': '~/.evergreen.yml',
            'csv': True,
            'json': False,
            'yml': False
        }
        # A list of builds, populated with --continue
        self.builds = []
        # The actual perf.json files, keyed as
        # self.results[0][variant_name][task_name]['data']['results']
        #             [0]['results'][thread_level]['ops_per_sec(_values)']
        self.results = []
        # Results aggregated over all builds, keyed as
        # self.agg_results[variant_name][task_name][test_name]['variance']
        # self.agg_results[variant_name][task_name][test_name]['ops_per_sec'] = []
        self.agg_results = {}

        # Contents of ~/.evergreen.yml or --evergreen-config
        self.evergreen_config = {}
        self.evergreen_client = None

    def parse_options(self):
        """Parse options in self.cli_args with argparse and put them in self.config."""
        self.parser = argparse.ArgumentParser(description="Analyze results from evergreen builds "
                                                          "created with multi_patch_builds.py",
                                              epilog="Use either --continue CONTINUE_FILE or list "
                                                     "of ids on command line.")
        self.parser.add_argument('--evergreen-config',
                                 help="Evergreen config file "
                                      "(default: {})".format(self.config['evergreen_config']))

        self.parser.add_argument('-c',
                                 '--config',
                                 action='append',
                                 help="Config file that can be used to supply same options as "
                                      "would be done on command line. Can be called multiple times "
                                      "and combined. On conflicts the last file on the command "
                                      "line wins")
        self.parser.add_argument('-C',
                                 '--continue',
                                 help="Read state serialized as yaml from CONTINUE, to continue "
                                      "operating on a series of submitted builds. Example: "
                                      "'multi_analysis.py --continue 12345.yml "
                                      "--analyze-results'")
        self.parser.add_argument('--csv',
                                 action='store_true',
                                 help="Output in csv format (default)")
        self.parser.add_argument('--json',
                                 action='store_true',
                                 help="Output in json format")
        self.parser.add_argument('--yml',
                                 action='store_true',
                                 help="Ouput in yml format")
        self.parser.add_argument('--out',
                                 help="File name to write output (print to stdout if omitted)")
        self.parser.add_argument('--graph-dir',
                                 help="Directory to save pyplot graphs in (default: no pyplot)")

        self.parser.add_argument('id',
                                 nargs='*',
                                 type=str,
                                 help="Space separated list of evergreen build ids")

        args = self.parser.parse_args(self.cli_args)

        # If one or more config files was specified, they have lowest precedence
        if args.config:
            for conf in args.config:
                conf = os.path.expanduser(conf)
                self.config.update(yaml.load(open(conf)))
        # Options given on command line have highest precedence
        for key, val in vars(args).iteritems():
            # Had to add val != False to this idiom. multi_patch_builds.py probably has same
            # issue: If you'd set a boolean option in config file, then argparse will provide
            # the value False and overwrite it.
            # This is still not general purpose, but sufficient for this script.
            if val is not None and val != False:
                self.config[key] = val

        if len(args.id) > 0 and 'continue' in self.config:
            raise OptionError('--continue and id on the command line are mutually exclusive.')

        if self.config['json'] or self.config['yml']:
            # Disable the default
            self.config['csv'] = False
        if self.config['json'] and self.config['yml']:
            raise OptionError('--csv, --json and --yml are mutually exclusive.')

        # If ids were given on the command line, build a "fake" list of builds out of them
        if 'id' in self.config and 'continue' not in self.config:
            for _id in self.config['id']:
                self.builds.append({'ID': _id, 'index': len(self.builds)})
        elif 'continue' in self.config:
            continue_file = os.path.expanduser(self.config['continue'])
            with open(continue_file) as yaml_file:
                self.builds = yaml.load(yaml_file)

        # Read evergreen config file, we need it when we use the REST API client
        path = os.path.expanduser(self.config['evergreen_config'])
        with open(path) as config_file:
            self.evergreen_config.update(yaml.load(config_file))
            # We have 2 different config files around. Rest of analysis uses a config.yml in
            # repo root, where the evergreen config is under the key "evergreen".
            # Unit tests must use this config file, so we need to support it
            if 'evergreen' in self.evergreen_config:
                self.evergreen_config = self.evergreen_config['evergreen']
        self.evergreen_client = evergreen_client.Client(self.evergreen_config)

    def evergreen_fetch_result_ids(self):
        """
        Get the tasks related to each build, and store the task_id that can be used to get results
        """
        for build in self.builds:
            build['result_ids'] = {}
            version_obj = self.evergreen_client.query_revision(build['ID'])
            for build_variant_id in version_obj['builds']:
                build_variant_id = build_variant_id

                build_variant_obj = self.evergreen_client.query_build_variant(build_variant_id)
                variant_name = build_variant_obj['variant']
                tasks_in_variant = {}
                for task_name, task_obj in build_variant_obj['tasks'].iteritems():
                    if task_name == 'compile':
                        continue
                    task_name = task_name

                    task_id = task_obj['task_id']
                    tasks_in_variant[task_name] = {'task_id': task_id,
                                                   'build_variant_id': build_variant_id}

                build['result_ids'][variant_name] = tasks_in_variant

    def evergreen_fetch_results(self):
        """Get the performance results json files for each task_id"""
        self.results = []
        for build in self.builds:
            build_results = {}
            for variant_name, tasks_in_variant in build['result_ids'].iteritems():
                build_results[variant_name] = {}
                for task_name, task_obj in tasks_in_variant.iteritems():
                    task_id = task_obj['task_id']
                    result_doc = self.evergreen_client.query_perf_results(task_id)
                    build_results[variant_name][task_name] = result_doc
            self.results.append(build_results)

    def _test_names_iterator(self, variant_name, task_name):
        """
        Generate an iterator over test names found in the fecthed perf.json results.

        ...more specifically in:
        self.results[0][variant_name][task_name]['data']['results'][*]['name']

        Implicit assumption is that all results[] have identical contents / names.
        """
        for result in self.results[0][variant_name][task_name]['data']['results']:
            yield result['name']

    def aggregate_results(self):
        """
        Aggregate self.results into self.agg_results.
        keyed as self.agg_results[variant_name][task_name][test_name][thread_level]
        """
        # I decided that the below is more readable with allowing the longest lines to be themselves
        # pylint: disable=line-too-long
        self.agg_results = {}
        for result in self.results:
            for variant_name, variant_result in result.iteritems():
                if not variant_name in self.agg_results:
                    self.agg_results[variant_name] = {}

                for task_name, task_result in variant_result.iteritems():
                    if not task_name in self.agg_results[variant_name]:
                        self.agg_results[variant_name][task_name] = {}

                    for test_result in task_result['data']['results']:
                        test_name = str(test_result['name'])
                        if not test_name in self.agg_results[variant_name][task_name]:
                            self.agg_results[variant_name][task_name][test_name] = {}

                        for thread_level, thread_result in test_result['results'].iteritems():
                            thread_level = int(thread_level)
                            if not thread_level in self.agg_results[variant_name][task_name][test_name]:
                                self.agg_results[variant_name][task_name][test_name][thread_level] = {'ops_per_sec': [], 'ops_per_sec_values': []}

                            agg_thread_level = self.agg_results[variant_name][task_name][test_name][thread_level]
                            agg_thread_level['ops_per_sec'].append(thread_result['ops_per_sec'])
                            agg_thread_level['ops_per_sec_values'].append(thread_result['ops_per_sec_values'])
        self.compute_aggregates()


    def compute_aggregates(self):
        """Compute aggregates (average, variance,...) of the values in self.agg_results"""
        for path, val in deep_dict_iterate(self.agg_results):
            if path[-1] == 'ops_per_sec' and isinstance(val, list):
                parent_obj = deep_dict_get(self.agg_results, path[0:-1])
                parent_obj['average'] = float(numpy.average(val))
                parent_obj['median'] = float(numpy.median(val))
                parent_obj['variance'] = float(numpy.var(val))
                parent_obj['variance_to_mean'] = (float(parent_obj['variance']) /
                                                  float(parent_obj['average']))
                parent_obj['min'] = min(val)
                parent_obj['max'] = max(val)
                parent_obj['range'] = parent_obj['max'] - parent_obj['min']
                parent_obj['range_to_median'] = (float(parent_obj['range']) /
                                                 float(parent_obj['median']))


    def write_results(self):
        """Print or write to file csv or json or yaml, depending on options"""
        file_handle = sys.stdout
        if 'out' in self.config:
            file_path = os.path.expanduser(self.config['out'])
            file_handle = open(file_path, 'w')

        if self.config['csv']:
            file_handle.write(self.csv_str())
        if self.config['json']:
            file_handle.write(self.json_str())
        if self.config['yml']:
            file_handle.write(self.yml_str())

        if 'out' in self.config:
            print("Wrote aggregated results to {}.".format(self.config['out']))

        if 'graph_dir' in self.config:
            self.graphs(self.config['graph_dir'])

    def csv_str(self):
        """Return self.agg_results as a CSV formatted string"""
        csv = ("Variant,Test,Thread level,Var/Mean,Variance,Average,Median,Min,Max,Range,"
               "Range/Median\n")

        for variant_name, variant_obj in sorted_iter(self.agg_results):
            for _, task_obj in sorted_iter(variant_obj):
                for test_name, test_obj in sorted_iter(task_obj):
                    for thread_level, thread_obj in sorted_iter(test_obj):
                        csv += "{},{},{},{},{},{},{},{},{},{},{}\n".format(
                            variant_name, test_name, thread_level,
                            thread_obj['variance_to_mean'],
                            thread_obj['variance'],
                            thread_obj['average'],
                            thread_obj['median'],
                            thread_obj['min'],
                            thread_obj['max'],
                            thread_obj['range'],
                            thread_obj['range_to_median'])
        return csv

    def json_str(self):
        """Return self.agg_results as JSON"""
        return json.dumps(self.agg_results, indent=4, sort_keys=True)

    def yml_str(self):
        """Return self.agg_results as JSON"""
        return yaml.dump(self.agg_results, default_flow_style=False)

    def graphs(self, directory):
        """Write some pyplot graphs into sub-directory"""
        if not os.path.isdir(directory):
            os.makedirs(directory)

        pyplot.style.use("ggplot")

        # Each variant is a separate graph
        metrics = ['variance_to_mean', 'average']
        for metric in metrics:
            for variant_name, variant_obj in self.agg_results.iteritems():
                # Get variance for each test
                variances = []
                test_names = []
                for path, val in deep_dict_iterate(variant_obj):
                    if path[-1] == metric:
                        variances.append(val)
                        test_names.append(path[1] + "." + str(path[2])) # test_name.thread_level

                axis = pyplot.subplot(111)
                pyplot.subplots_adjust(bottom=0.3)
                width = 0.8
                axis.bar(range(len(test_names)), variances, width=width)
                axis.set_xticks(numpy.arange(len(test_names)) + width/2)
                axis.set_xticklabels(test_names, rotation=90)
                axis.tick_params(axis='both', which='major', labelsize=5)
                axis.tick_params(axis='both', which='minor', labelsize=5)
                pyplot.title(variant_name + ' : ' + metric)
                # Save to file
                file_name = variant_name + '--' + metric + '.png'
                path = os.path.join(directory, file_name)
                pyplot.savefig(path)
        print("Wrote graphs to {}{}.".format(directory, os.sep))

def deep_dict_iterate(deep_dict, path=None, to_return=None):
    """
    Iterate over the lowest level (the leaves) of self.agg_results,

    without needing a for loop for each level separately.
    Returns [ ([key1, key2, key3], value), (...), ... )]
    """
    if path is None:
        path = []
    if to_return is None:
        to_return = []
    if isinstance(deep_dict, dict):
        #pylint: disable=unused-variable
        for key in sorted_keys(deep_dict):
            pair = deep_dict_iterate(deep_dict[key], path + [key], to_return)
            # Avoid circular references on the way back
            if pair != to_return:
                to_return.append(pair)
        return to_return
    else:
        return path, deep_dict

def deep_dict_get(deep_dict, path):
    """Return deep_dict[path[0]][path[1]..."""
    value = deep_dict
    for key in path:
        value = value[key]
    return value

def deep_dict_set(deep_dict, path, value):
    """Set deep_dict[path[0]][path[1]]... = value"""
    obj = deep_dict
    for key in path[0:-1]:
        obj = obj[key]
    key = path[-1]
    obj[key] = value

def sorted_iter(a_dict):
    """Like dict.iteritems(), but sorts keys first."""
    keys = a_dict.keys()
    keys.sort()
    for key in keys:
        yield key, a_dict[key]

def sorted_keys(a_dict):
    """Like dict.keys(), but sorts keys first."""
    keys = a_dict.keys()
    keys.sort()
    for key in keys:
        yield key


def main(cli_args=None):
    """Main function"""
    if cli_args is None:
        cli_args = sys.argv[1:]

    multi_analysis = MultiEvergreenAnalysis(cli_args)

    try:
        multi_analysis.parse_options()
    except OptionError as err:
        multi_analysis.parser.print_usage(file=sys.stderr)
        print("", file=sys.stderr)
        print(err, file=sys.stderr)
        exit(1)

    multi_analysis.evergreen_fetch_result_ids()
    multi_analysis.evergreen_fetch_results()
    multi_analysis.aggregate_results()
    multi_analysis.write_results()

if __name__ == '__main__':
    main()
