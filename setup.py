#!/usr/bin/env python2.7
"""
Setup DSI

This is a DSI wide setup file, however it currently only installs aws_tools to cleanup. This may get
extended to install all of DSI as part of https://jira.mongodb.org/browse/PERF-1217.
"""
# pylint: disable=no-name-in-module,import-error, invalid-name, E1101
# https://github.com/PyCQA/pylint/issues/73

from setuptools import setup

# pylint: disable=line-too-long
# The minimum set required to run.
# Different from requirements.txt, this is the complete python environment for the project
# including tests etc.
# See 'requires v requirements<https://packaging.python.org/discussions/install-requires-vs-requirements/>'.
# pylint: disable=invalid-name
install_requirements = [
    'boto3==1.4.7',
    'click~=7.0',
    'colorama==0.3.9',
    'dnspython==1.15.0',
    'enum34==1.1.6',
    'future==0.16.0',
    'jira==1.0.15',
    'jinja2==2.10',
    'keyring==10.6.0',
    'numpy==1.13.3',
    'pymongo==3.7.2',
    'python-dateutil~=2.7.0',
    'PyYAML~=5.1',
    'requests~=2.22.0',
    'scipy==1.1.0',
    'signal-processing @ git+ssh://git@github.com/10gen/signal-processing'
    '@0.2.5',
    'structlog~=19.1.0',
    'tenacity==5.0.4',
]
extras_require = {
    'Plotting': ['matplotlib==2.1.0']
}
setup(
    name='DSI',
    version='1.0',
    description='Tools for running realistic performance tests on AWS resources',
    # Including bin.common so that we can access it from aws_tools.
    packages=['aws_tools',
              'bin',
              'bin.common',
              'bin.testcontrollib',
              'analysis',
              'analysis.evergreen'],
    install_requires=install_requirements,
    extras_require=extras_require,
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
            'detect-changes = analysis.signal_processing_entry_points:DETECT_CHANGES',
            'detect-outliers = analysis.signal_processing_entry_points:DETECT_OUTLIERS',
            'etl-jira-mongo = analysis.signal_processing_entry_points:ETL_JIRA_MONGO',
            'change-points = analysis.signal_processing_entry_points:CHANGE_POINTS',
            'outliers = analysis.signal_processing_entry_points:OUTLIERS',
            'etl-evg-mongo = analysis.signal_processing_entry_points:ETL_EVG_MONGO',
            'compare-algorithms = analysis.signal_processing_entry_points:COMPARE_ALGORITHMS',
        ]
    }
)
