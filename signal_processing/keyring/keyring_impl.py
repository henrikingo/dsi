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

LOG = structlog.getLogger(__name__)

# This doesn't fail to aid testing, but you shouldn't import this class directly use the package
# like from signal_processing.keyring import Keyring
try:
    import keyring
except (ImportError, RuntimeError):
    # This is Logged in __init__.py
    pass


class NoopKeyring(object):
    """ Noop keyring implementation. """

    # pylint: disable=unused-argument, no-self-use
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
        :rtype: str or None.
        """
        return None

    def write(self, property_name, value):
        """ Write name property to keyring.

        :parameter str property_name: The name of the property to read.
        :parameter object value: The property to write.
        """
        pass

    def delete(self, property_name):
        """ Delete property from keyring.

        :parameter str property_name: The name of the property to read.
        """
        pass


class Keyring(NoopKeyring):
    """ Read / Write properties from keyring. """

    def read(self, property_name):
        """ Read property from keyring.
        :parameter str property_name: The name of the property to read.

        :return: The property.
        """
        return keyring.get_password(self.service_name, property_name)

    def write(self, property_name, value):
        """ Write name property to keyring.

        :parameter str property_name: The name of the property to read.
        :parameter object value: The property to write.
        """
        keyring.set_password(self.service_name, property_name, value)

    def delete(self, property_name):
        """ Delete property from keyring.

        :parameter str property_name: The name of the property to read.
        """
        keyring.delete_password(self.service_name, property_name)
