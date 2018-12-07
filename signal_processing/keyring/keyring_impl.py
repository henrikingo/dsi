"""
Keyring Implementation support. Don't import this directly unless you are testing.

use like:

    from signal_processing.keyring import Keyring

    keyring = signal_processing.keyring.Keyring('My Cool Server')
    username, password = keyring.read('credentials')
    try:
        # do something
    except:
        pass
    keyring.write('credentials', [username, password])

There is a context manager to simplify jira usage, see :func:
`signal_processing.jira_helpers.jira_keyring_helper`.
"""
from __future__ import print_function
import structlog
import keyring

LOG = structlog.getLogger(__name__)


class Keyring(object):
    """ Read / Write properties from keyring. """

    def __init__(self, service_name):
        """
        Create a noop keyring.

        :param str service_name: The service name to use to save the properties.
        """
        self.service_name = service_name

    def read(self, property_name):
        """ Read property from keyring.
        :parameter str property_name: The name of the property to read.

        :return: The property.
        """
        try:
            return keyring.get_password(self.service_name, property_name)
        except RuntimeError as rte:
            LOG.error('exception', exc_info=1)
            if 'No recommended backend was available.' not in rte.message:
                raise rte
            return None

    def write(self, property_name, value):
        """ Write name property to keyring.

        :parameter str property_name: The name of the property to read.
        :parameter object value: The property to write.
        """
        try:
            keyring.set_password(self.service_name, property_name, value)
        except RuntimeError as rte:
            if 'No recommended backend was available.' not in rte.message:
                raise rte

    def delete(self, property_name):
        """ Delete property from keyring.

        :parameter str property_name: The name of the property to read.
        """
        try:
            keyring.delete_password(self.service_name, property_name)
        except RuntimeError as rte:
            if 'No recommended backend was available.' not in rte.message:
                raise rte
