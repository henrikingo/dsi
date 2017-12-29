#!/usr/bin/env python2.7
""" Run javascript tests to check correctness """

from functools import partial
import logging
import os

from host import make_workload_runner_host
from thread_runner import run_threads
from utils import mkdir_p

LOG = logging.getLogger(__name__)

SCRIPT_NAMES = {
    'validate-indexes-and-collections': 'run_validate_collections.js',
    'db-hash-check': 'run_check_repl_dbhash.js'
}


def jstest_one_host(config, mongo_uri, reports_dir, current_test_id, name):
    '''
    Run a jstest against one host.

    :param dict(ConfigDict) config: The system configuration.
    :param string mongo_uri: The mongo URI of the host to check
    :param string reports_dir: the report directory.
    :param string current_test_id: The identifier for this test.
    :param string name: The name of the jstest to run.
    Valid names are the keys from SCRIPT_NAMES.
 '''

    directory = os.path.join(reports_dir, current_test_id, 'db-correctness', name)
    filename = os.path.join(directory, mongo_uri)
    mkdir_p(directory)
    client_host = make_workload_runner_host(config)
    script = SCRIPT_NAMES[name]

    with open(filename, 'wb+', 0) as out:
        error = client_host.exec_command(
            'bin/mongo {} {}/{}'.format(mongo_uri, config['test_control']['jstests_dir'], script),
            out=out,
            err=out)
        if error:
            # The return code of the script call is significant. If it is non-zero we put 1 at the
            # end of the file to indicate failure. The analysis script rules.py checks the number of
            # the last line.
            out.write("ERROR\n1")
            LOG.error("Failed %s correctness check on %s", name, mongo_uri)
        else:
            # Indicate that the script returned 0. This is checked by the analysis script rules.py.
            out.write("0")
    client_host.close()


def validate_one_host(config, mongo_uri, reports_dir, current_test_id, replica_checks=False):
    ''' Run the correctness tests for one host.
    If run on a replica set it is expected to be called against the primary.

    :param dict(ConfigDict) config: The system configuration.
    :param string mongo_uri: The mongo URI of the host to check
    :param string reports_dir: the report directory.
    :param string current_test_id: The identifier for this test.
    :param boolean replica_checks: Indicates if the host is part of a replica set,
    and should have the replica correctness checks run also.
    '''

    LOG.debug("Validating host %s", mongo_uri)
    jstest_one_host(config, mongo_uri, reports_dir, current_test_id,
                    'validate-indexes-and-collections')
    if replica_checks:
        LOG.debug("DBHash on host %s", mongo_uri)
        jstest_one_host(config, mongo_uri, reports_dir, current_test_id, 'db-hash-check')


def run_validate(config, current_test_id=None, reports_dir='reports'):
    ''' Validate the DB after a test

    :param dict(ConfigDict) config: The system configuration.
    :param string current_test_id: Indicates the id for the test related to the current set of
    commands. If there is not a specific test related to the current set of commands, the value of
    current_test_id will be None.
    :param string reports_dir: the report directory.
    '''

    LOG.debug('In run_validate before jstests_dir check')
    # If jstests_dir doesn't exist or is falsey, don't do anything
    if 'jstests_dir' not in config['test_control'] or not config['test_control']['jstests_dir']:
        LOG.warning('No jstests_dir specified. Skipping validate')
        return

    LOG.info('In run_validate')
    # Run the checks
    if 'standalone' in config['mongodb_setup']['validate']:
        run_threads([
            partial(validate_one_host, config, primary, reports_dir, current_test_id, False)
            for primary in config['mongodb_setup']['validate']['standalone']
        ])
    if 'primaries' in config['mongodb_setup']['validate']:
        run_threads([
            partial(validate_one_host, config, primary, reports_dir, current_test_id, True)
            for primary in config['mongodb_setup']['validate']['primaries']
        ])