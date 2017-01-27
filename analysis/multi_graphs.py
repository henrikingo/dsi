#!/usr/bin/env python2.7
"""
Create pyplot graphs from data that was output from multi_analysis.py.

Note: No unit tests for this file, the pyplot module is heavy on dependencies.
"""

from __future__ import print_function

import argparse
import json
import os
import sys

import matplotlib.pyplot as pyplot
import numpy
import yaml

import deep_dict

class OptionError(Exception):
    """Exception raised for erroneous command line options."""
    pass

class MultiAnalysisGraphs(object):
    """
Create pyplot graphs from data that was output from multi_analysis.py.
    """

    def __init__(self, cli_args=None):
        """Constructor."""
        self.cli_args = cli_args
        # Instance of argparse
        self.parser = None
        # Default config options
        self.config = {
            'csv': True,
            'json': False,
            'yml': False,
            'graph_dir': 'multi_graphs_out'
        }
        # Input data. This is the output from multi_analysis.py.
        self.agg_results = {}

    def parse_options(self):
        """Parse options in self.cli_args with argparse and put them in self.config."""
        self.parser = argparse.ArgumentParser(description="Create pyplot graphs from "
                                                          "multi_analysis.py output.")
        self.parser.add_argument('-c',
                                 '--config',
                                 action='append',
                                 help="Config file that can be used to supply same options as "
                                      "would be done on command line. Can be called multiple times "
                                      "and combined. On conflicts the last file on the command "
                                      "line wins")
        self.parser.add_argument('--csv',
                                 action='store_true',
                                 help="Input is in csv format (default)")
        self.parser.add_argument('--json',
                                 action='store_true',
                                 help="Input is in json format")
        self.parser.add_argument('--yml',
                                 action='store_true',
                                 help="Input is in yml format")
        self.parser.add_argument('--input',
                                 help="File name for input data (read stdin if omitted)")
        self.parser.add_argument('--graph-dir',
                                 help="Directory to save pyplot graphs (default: multi_graphs_out)")

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

        if self.config['json'] or self.config['yml']:
            # Disable the default
            self.config['csv'] = False
        if self.config['json'] and self.config['yml']:
            raise OptionError('--csv, --json and --yml are mutually exclusive.')

    def read_agg_results(self):
        """Read csv or json or yaml, depending on options"""
        file_handle = sys.stdin
        if 'input' in self.config:
            file_path = os.path.expanduser(self.config['input'])
            file_handle = open(file_path)

        if self.config['csv']:
            self.parse_csv(file_handle)
        if self.config['json']:
            self.parse_json(file_handle)
        if self.config['yml']:
            self.parse_yml(file_handle)

        if 'input' in self.config:
            file_handle.close()
            print("Successfully read data from {}.".format(self.config['input']))

    def parse_csv(self, file_handle):
        """Parse csv input_data into self.agg_results"""
        input_data = [line.strip() for line in file_handle.readlines()]
        # Ignore first line, which is the header
        input_data.pop(0)
        for line in input_data:
            fields = line.split(",")
            keys = fields[0:4]
            thread_obj = {}
            thread_obj['variance_to_mean'] = float(fields[4])
            thread_obj['variance'] = float(fields[5])
            thread_obj['average'] = float(fields[6])
            thread_obj['median'] = float(fields[7])
            thread_obj['min'] = float(fields[8])
            thread_obj['max'] = float(fields[9])
            thread_obj['range'] = float(fields[10])
            thread_obj['range_to_median'] = float(fields[11])
            deep_dict.set_value(self.agg_results, keys, thread_obj)

    def parse_json(self, file_handle):
        """Parse json input_data into self.agg_results"""
        self.agg_results = json.load(file_handle)

    def parse_yml(self, file_handle):
        """Parse yaml input_data into self.agg_results"""
        self.agg_results = yaml.load(file_handle)

    def separate_fio_tests(self):
        """Separate fio tests to separate graphs for readability"""
        fio_tests = {}
        mongodb_tests = {}
        for variant_name, variant_obj in self.agg_results.iteritems():
            for task_name, task_obj in variant_obj.iteritems():
                for test_name, test_obj in task_obj.iteritems():
                    key = [variant_name, task_name, test_name]
                    if test_name[0:3] == 'mc_':
                        deep_dict.set_value(fio_tests, key, test_obj)
                    else:
                        deep_dict.set_value(mongodb_tests, key, test_obj)

        return mongodb_tests, fio_tests

    def graphs(self):
        """Write some pyplot graphs into sub-directory"""
        directory = os.path.expanduser(self.config['graph_dir'])
        if not os.path.isdir(directory):
            os.makedirs(directory)

        pyplot.style.use("ggplot")

        # Each variant is a separate graph
        # Second value is whether to use logarithmic y-axis
        metrics = [('variance_to_mean', False),
                   ('range_to_median', False),
                   ('average', False),
                   ('max', False),
                   ('max', True)]

        # Strings used in filenames for output files
        dataset_names = ["", "--fio"]

        for metric, log in metrics:
            dataset_index = -1
            for dataset in self.separate_fio_tests():
                dataset_index += 1
                # Separate set of graphs for each variant
                for variant_name, variant_obj in dataset.iteritems():
                    # Get variance for each test
                    yvalues = []
                    yvalues_median = []
                    yvalues_min = []
                    test_names = []
                    for path, val in deep_dict.iterate(variant_obj):
                        if path[-1] == metric:
                            yvalues.append(val)
                            test_names.append(path[1] + "." + str(path[2])) # test_name.thread_level
                            if metric == 'max':
                                # For the 'max' graph we actually print a stacked bar chart with
                                # min-median-max
                                median_key = [path[0], path[1], path[2], 'median']
                                median_val = deep_dict.get_value(variant_obj, median_key)
                                yvalues_median.append(median_val)
                                min_key = [path[0], path[1], path[2], 'min']
                                min_val = deep_dict.get_value(variant_obj, min_key)
                                yvalues_min.append(min_val)

                    pyplot.figure() # Reset canvas between loops
                    axis = pyplot.subplot(111)
                    pyplot.subplots_adjust(bottom=0.3)
                    width = 0.8
                    xvalues = range(len(test_names))

                    axis.bar(xvalues, yvalues, width=width, log=log)
                    if metric == 'max':
                        # pyplot is stupid and just draws these on top of each other.
                        # So one must start with the max value and go downward from there.
                        axis.bar(xvalues, yvalues_median, width=width, color='#0055ff', log=log)
                        axis.bar(xvalues, yvalues_min, width=width, color='#0000ff', log=log)

                    axis.set_xticks(numpy.arange(len(test_names)) + width/2)
                    axis.set_xticklabels(test_names, rotation=90)
                    axis.tick_params(axis='both', which='major', labelsize=5)
                    axis.tick_params(axis='both', which='minor', labelsize=5)
                    pyplot.title(variant_name + ' : ' + metric)

                    # Save to file
                    file_name_postfix = ""
                    if log:
                        file_name_postfix += '--log'
                    file_name_postfix += dataset_names[dataset_index]

                    file_name = variant_name + '--' + metric + file_name_postfix + '.png'
                    path = os.path.join(directory, file_name)
                    pyplot.savefig(path, dpi=500, format='png')
        print("Wrote graphs to {}{}.".format(directory, os.sep))

def main(cli_args=None):
    """Main function"""
    if cli_args is None:
        cli_args = sys.argv[1:]

    multi_graphs = MultiAnalysisGraphs(cli_args)

    try:
        multi_graphs.parse_options()
    except OptionError as err:
        multi_graphs.parser.print_usage(file=sys.stderr)
        print("", file=sys.stderr)
        print(err, file=sys.stderr)
        exit(1)

    multi_graphs.read_agg_results()
    multi_graphs.graphs()

if __name__ == '__main__':
    main()
