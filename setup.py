#!/usr/bin/env python2.7
"""
Setup DSI

This is a DSI wide setup file, however it currently only installs aws_tools to cleanup. This may get
extended to install all of DSI as part of https://jira.mongodb.org/browse/PERF-1217.

"""

from setuptools import setup

setup(
    name='DSI',
    version='1.0',
    description='Tools for running realistic performance tests on AWS resources',
    # Including bin.common so that we can access it from aws_tools.
    packages=['aws_tools', 'bin.common'],
    install_requires=['boto3==1.4.7', 'argparse==1.4.0'],
    use_2to3=True,
    entry_points={
        'console_scripts': [
            'delete-stranded-vpcs = aws_tools.entry_points:delete_stranded_vpcs',
            'delete-cluster = aws_tools.entry_points:delete_cluster_by_tag',
            'delete-runner-cluster = aws_tools.entry_points:delete_cluster_for_runner',
            'delete-task-cluster = aws_tools.entry_points:delete_cluster_for_task'
        ]
    })
