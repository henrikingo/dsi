import logging
import os
import subprocess


LOG = logging.getLogger(__name__)


def source(shell_file):
    """
    Sources the provided shell file and updates os.environ.

    Adapted from http://stackoverflow.com/a/3505826.
    """
    command = ['bash', '-c', 'source {0} && env'.format(shell_file)]

    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdoutdata, stderrdata = proc.communicate()
    if proc.returncode != 0:
        LOG.error('Failed to source file: %s, %s', shell_file, stderrdata)
        return False
    for line in stdoutdata.split('\n'):
        key, _, value = line.partition('=')
        os.environ[key] = value

    return True
