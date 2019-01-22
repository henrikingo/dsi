#!/usr/bin/env python2.7
"""
Setup DSI

This is a DSI wide setup file, however it currently only installs aws_tools to cleanup. This may get
extended to install all of DSI as part of https://jira.mongodb.org/browse/PERF-1217.
"""
# pylint: disable=no-name-in-module,import-error, invalid-name, E1101
# https://github.com/PyCQA/pylint/issues/73
import sys
import warnings
import distutils.core
from distutils.command.build_ext import build_ext
from distutils.errors import (CCompilerError, DistutilsExecError,
                              DistutilsPlatformError)

import platform
from setuptools import setup


class CustomBuildExt(build_ext):
    """
    Allow C extension building to fail.

    The C extension speeds up E-Divisive calculation, but is not essential.
    """

    warning_message = '''
********************************************************************
WARNING: %s could not
be compiled. No C extensions are essential for signal processing to run,
although they do result in significant speed improvements.
%s
'''
    def run(self):
        """
        Run a custom build, errors are ignored.
        """
        try:
            build_ext.run(self)
        except DistutilsPlatformError:
            e = sys.exc_info()[1]
            sys.stdout.write('%s\n' % str(e))
            warnings.warn(self.warning_message % ("Extension modules",
                                                  "There was an issue with "
                                                  "your platform configuration"
                                                  " - see above."))

    def build_extension(self, ext):
        """
        Build the extension, ignore any errors.
        """
        name = ext.name
        if sys.version_info[:3] >= (2, 7, 0):
            try:
                build_ext.build_extension(self, ext)
            except build_errors:
                e = sys.exc_info()[1]
                sys.stdout.write('%s\n' % str(e))
                warnings.warn(self.warning_message % ("The %s extension "
                                                      "module" % (name,),
                                                      "failed to compile."))
        else:
            warnings.warn(self.warning_message % ("The %s extension "
                                                  "module" % (name,),
                                                  "only supports python "
                                                  ">= 2.7."))

if sys.platform == 'win32':
    # distutils.msvc9compiler can raise an IOError when failing to
    # find the compiler
    build_errors = (CCompilerError, DistutilsExecError,
                    DistutilsPlatformError, IOError)
else:
    build_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError)

ext_modules = [
    distutils.core.Extension(
        'signal_processing.native._e_divisive',
        sources=['./signal_processing/native/e_divisive.c'],
        extra_compile_args=["-O3"],
        extra_link_args=[] if 'Darwin' in platform.system() else ["-shared"])
]
extra_opts = {}

if "--no_ext" in sys.argv:
    sys.argv.remove("--no_ext")
elif (sys.platform.startswith("java") or
      sys.platform == "cli" or
      "PyPy" in sys.version):
    sys.stdout.write("""
*****************************************************\n
The optional C extensions are currently not supported\n
by this python implementation.\n
*****************************************************\n
""")
else:
    extra_opts['ext_modules'] = ext_modules

# pylint: disable=line-too-long
# The minimum set required to run.
# Different from requirements.txt, this is the complete python environment for the project
# including tests etc.
# See 'requires v requirements<https://packaging.python.org/discussions/install-requires-vs-requirements/>'.
# pylint: disable=invalid-name
install_requirements = ['boto3==1.4.7',
                        'click==6.7',
                        'colorama==0.3.9',
                        "dnspython==1.15.0",
                        "jira==1.0.15",
                        "jinja2==2.10",
                        "numpy==1.13.3",
                        'pymongo==3.6.1',
                        "python-dateutil==2.6.1",
                        'PyYAML==3.12',
                        'requests==2.18.4',
                        'scipy==1.1.0',
                        'structlog==18.1.0',
                        'future==0.16.0',
                        'keyring==10.6.0']
extras_require = {
    'Plotting':  ['matplotlib==2.1.0']
}
setup(
    name='DSI',
    version='1.0',
    description='Tools for running realistic performance tests on AWS resources',
    # Including bin.common so that we can access it from aws_tools.
    packages=['aws_tools',
              'bin',
              'bin.common',
              'signal_processing',
              'signal_processing.change_points',
              'signal_processing.commands',
              'signal_processing.commands.change_points',
              'signal_processing.commands.outliers',
              'signal_processing.keyring',
              'signal_processing.native',
              'signal_processing.outliers',
              'signal_processing.profiling',
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
            'detect-changes = signal_processing.detect_changes:main',
            'detect-outliers = signal_processing.detect_outliers:main',
            'etl-jira-mongo = signal_processing.etl_jira_mongo:main',
            'change-points = signal_processing.change_points_cli:cli',
            'outliers = signal_processing.outliers_cli:cli',
            'etl-evg-mongo = signal_processing.etl_evg_mongo:etl',
            'compare-algorithms = signal_processing.profiling.cli:cli',
        ]
    },
    cmdclass={"build_ext": CustomBuildExt},
    **extra_opts
)
