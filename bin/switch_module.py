#!/usr/bin/env python3
"""
Modify github url of dsi module in etc/system_perf.yml.
"""
from __future__ import print_function

import argparse
import sys
import warnings

import ruamel.yaml as yaml  # Avoids exceptions on duplicate anchors

warnings.simplefilter('ignore', yaml.error.UnsafeLoaderWarning)
warnings.simplefilter('ignore', yaml.error.ReusedAnchorWarning)


def modify_file(args):
    """Read-modify-write etc/system_perf.yml."""
    y = yaml.YAML()
    y.default_flow_style = False
    y.indent(mapping=2, sequence=4, offset=2)
    evergreen_yaml = {}
    with open(args.file) as yaml_file:
        evergreen_yaml = y.load(yaml_file)

    if 'modules' in evergreen_yaml and isinstance(evergreen_yaml['modules'], list):
        for module in evergreen_yaml['modules']:
            if module['name'] == args.name:
                module['repo'] = args.repo
                module['branch'] = args.branch
                with open(args.file, "w") as yaml_file:
                    y.dump(evergreen_yaml, yaml_file)
                _print_success(args, module, y)
                break


def _print_success(args, module, y):
    print('Found and edited the following module:\n')
    y.dump([module], sys.stdout)
    print('In addition, this screwed up a lot of indentation for you. Sorry!')
    print('To undo this change: git checkout {path}'.format(path=args.file))


def parse_command_line():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Edit github path for evergreen modules in evergreen yaml files.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-f',
                        '--file',
                        default='etc/system_perf.yml',
                        help='Evergreen yml file to modify.')
    parser.add_argument('-n',
                        '--name',
                        default='dsi',
                        help='Name of the evergreen module to modify.')
    parser.add_argument('-r',
                        '--repo',
                        default='git@github.com:henrikingo/dsi.git',
                        help='Use this repo instead.')
    parser.add_argument('-b', '--branch', default='stable', help='Use this branch instead.')
    args = parser.parse_args()
    return args


def main():
    """ Main function """
    args = parse_command_line()
    modify_file(args)


if __name__ == '__main__':
    main()
