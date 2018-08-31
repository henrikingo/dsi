#!/usr/bin/env python2.7
"""
Setup DSI

This is a DSI wide setup file, however it currently only installs aws_tools to cleanup. This may get
extended to install all of DSI as part of https://jira.mongodb.org/browse/PERF-1217.
"""
from setuptools import setup

# pylint: disable=line-too-long
# The minimum set required to run.
# Different from requirements.txt, this is the complete python environment for the project
# including tests etc.
# See 'requires v requirements<https://packaging.python.org/discussions/install-requires-vs-requirements/>'.
# pylint: disable=invalid-name
install_requirements = ['boto3==1.4.7',
                        'click==6.7',
                        'colorama===0.3.9',
                        'pymongo==3.6.1',
                        'PyYAML===3.12',
                        'requests===2.18.4',
                        'scipy==1.1.0',
                        'structlog===18.1.0']

setup(
    name='DSI',
    version='1.0',
    description='Tools for running realistic performance tests on AWS resources',
    # Including bin.common so that we can access it from aws_tools.
    packages=['aws_tools',
              'bin',
              'bin.common',
              'signal_processing',
              'signal_processing.commands',
              'signal_processing.profiling',
              'analysis',
              'analysis.evergreen'],
    install_requires=install_requirements,
    # Cannot zip due to usage of __file__.
    zip_safe=False,
    use_2to3=True,
    entry_points={
        'console_scripts': [
            'delete-stranded-vpcs = aws_tools.entry_points:delete_stranded_vpcs',
            'delete-cluster = aws_tools.entry_points:delete_cluster_by_tag',
            'delete-runner-cluster = aws_tools.entry_points:delete_cluster_for_runner',
            'delete-task-cluster = aws_tools.entry_points:delete_cluster_for_task',
            'delete-placement-groups = aws_tools.entry_points:delete_placement_groups',
            'detect-changes = signal_processing.detect_changes:main',
            'etl-jira-mongo = signal_processing.etl_jira_mongo:main',
            'change-points = signal_processing.change_points:cli',
            'etl-evg-mongo = signal_processing.etl_evg_mongo:etl',
            'compare-algorithms = signal_processing.profiling.cli:cli',
        ]
    },
)
