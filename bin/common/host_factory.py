"""
Generate the right type of host object and return it or run commands against it
"""

import logging

from common.local_host import LocalHost
from common.remote_host import RemoteHost
from common.log import IOLogAdapter

LOG = logging.getLogger(__name__)
# This stream only log error or above messages
ERROR_ONLY = logging.getLogger('error_only')

INFO_ADAPTER = IOLogAdapter(LOG, logging.INFO)
WARN_ADAPTER = IOLogAdapter(LOG, logging.WARN)


def make_host(host_info, ssh_user, ssh_key_file, mongodb_auth_settings=None):
    """
    Create a host object based off of host_ip_or_name. The code that receives the host is
    responsible for calling close on the host instance. Each RemoteHost instance can have 2*n+1 open
    sockets (where n is the number of exec_command calls with Pty=True) otherwise n is 1 so there is
    a max of 3 open sockets.

    :param namedtuple host_info: Public IP address or the string localhost, category and offset
    :param str ssh_user: The user id to use
    :param str ssh_key_file: The keyfile to use
    :rtype: Host
    """
    if host_info.ip_or_name in ['localhost', '127.0.0.1', '0.0.0.0']:
        LOG.debug("Making localhost for %s", host_info.ip_or_name)
        host = LocalHost(mongodb_auth_settings)
    else:
        LOG.debug("Making remote host for %s", host_info.ip_or_name)
        host = RemoteHost(host_info.ip_or_name, ssh_user, ssh_key_file, mongodb_auth_settings)
    host.alias = "{category}.{offset}".format(category=host_info.category, offset=host_info.offset)
    return host
