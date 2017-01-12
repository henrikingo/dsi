#!/usr/bin/env python2.7
'''
Update the target test list for a test_control.yml file

'''

import sys

import argparse
import yaml


def testlist_update(new_target, input_filename=None, output_filename=None):
    '''Read in the file filename or test_control.yml, update the
    test_list entry, and write the file back out

    :type new_target: str
    :type input_filename: str

    '''

    if not input_filename:
        input_filename = 'test_control.yml'
    if not output_filename:
        output_filename = input_filename

    with open(input_filename) as yaml_file:
        test_control = yaml.load(yaml_file)

    # Only update the test_list if there is a workload_config
    for run in test_control['run']:
        if 'workload_config' in run:
            if isinstance(run['workload_config'], dict):
                run['workload_config']['test_list'] = new_target

    with open(output_filename, 'w') as yaml_file:
        yaml_file.write(yaml.dump(test_control))


def main(argv):
    ''' Main function for updating testlist '''

    parser = argparse.ArgumentParser(description='Update test_list argument in test_control.yml')
    parser.add_argument('-i',
                        '--input-file',
                        default='test_control.yml',
                        help='Input file to update')
    parser.add_argument('-o',
                        '--output-file',
                        help='Output file. Defaults to inplace update')
    parser.add_argument('testlist',
                        help='New testlist to use')

    args = parser.parse_args(argv)
    testlist_update(args.testlist, args.input_file, args.output_file)

if __name__ == '__main__':
    main(sys.argv[1:])
