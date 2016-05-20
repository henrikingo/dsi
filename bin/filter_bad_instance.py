#!/usr/bin/env python

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

"""Filter out bad instances"""
from __future__ import print_function
import sys
import re

# to find and print list of bad instances.
# take input from stdin
# print to stdout
# no output if no "bad" instance found

def check_bad_instance(line):
    '''
    how to find "bad" instance:
        we will check avg for fio clat (completion latency),
        if clat_avg <= 7000 usec, we will consider it good for test run
        there are two SSDs for each instance, it will check both disks
        any disk fio test failure will cause the instance to be recreated

    format of input without module:
    aws_instance.member (remote-exec):  clat (usec): min=104, max=93265, avg=19980.3, stdev=20666.44
    aws_instance.member (remote-exec):  clat (usec): min=105, max=97675, avg=20374.5, stdev=20305.26

    >>> check_bad_instance("aws_instance.member.1 (remote-exec):     \
        clat (usec): min=104, max=93265, avg=19980.03, stdev=20666.44")
    'aws_instance.member.1'
    >>> check_bad_instance("aws_instance.member.1 (remote-exec):     \
        clat (usec): min=104, max=93265, avg=1980.03, stdev=20666.44") == None
    True

    format for input with terraform module, in order to taint a module resource,
    we need make sure properly mark module name
        example:
            module.mongod_instance_with_placement_group.aws_instance.member
        ->
            terraform taint -module=mongod_instance_with_placement_group aws_instance.member
    >>> check_bad_instance("module.cluster.mongod_instance.aws_instance.member (remote-exec):\
        clat (usec): min=104, max=610269, avg=13316.92, stdev=9050.75")
    '-module=cluster.mongod_instance aws_instance.member'
    >>> check_bad_instance("module.cluster.mongod_instance.aws_instance.member \
        (remote-exec):     clat (usec): min=104, max=610269, avg=3316.92, stdev=9050.75") == None
    True

    Tests:
        FIXME: change testcases to unittest
    '''

    m_msec = re.search(r'clat \(msec\):', line)

    if m_msec:
        # sometime it is really bad, clat will be in msec level
        i = re.search(r'(aws_instance.[a-zA-Z0-9_\.]+) ', line)
        if i:
            return i.group(1)
    else:
        t_usec = re.search(r' avg=([0-9\.]+),', line)
        if t_usec != None and float(t_usec.group(1)) > 7000.00:
            # search for instance belongs to a module
            i = re.search(r'module\.([a-zA-Z0-9_\.]+)\.(aws_instance.[a-zA-Z0-9_\.]+) ', line)
            if i:
                return "-module=" + i.group(1) + " " + i.group(2)

            i = re.search(r'(aws_instance.[a-zA-Z0-9_\.]+) ', line)
            if i:
                return i.group(1)

    return None

def main():
    '''main function'''
    for line in sys.stdin:
        has_bad_instance = check_bad_instance(line)
        if has_bad_instance != None:
            print(has_bad_instance)

if __name__ == '__main__':
    main()
