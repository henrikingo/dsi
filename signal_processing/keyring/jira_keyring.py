"""
Wrap jira access and keyring support in a context manager.

Usage:

    from signal_processing.jira_helpers import jira_keyring_helper

    with jira_keyring_helper() as jira:
        issue = jira.issue('BF-1234')

The previous code will use a keyring if available or prompt for username / password if no keyring
or no stored credentials.

If the code in the context manager completes without an exception and the credentials have changed
then the keyring data will be updated if it has changed.

"""
from __future__ import print_function

from contextlib import contextmanager
from keyring.errors import PasswordSetError

from jira.exceptions import JIRAError

from signal_processing.etl_jira_mongo import JiraCredentials, JIRA_URL, new_jira_client
from signal_processing.keyring.keyring_impl import Keyring
import structlog

LOG = structlog.getLogger(__name__)

KEYRING_SERVICE_NAME = 'signal processing'
""" The keyring service name. """

KEYRING_PROPERTY_NAME = 'jira_username_and_password'
""" The keyring property name. """


@contextmanager
def jira_keyring(jira_user=None, jira_password=None, use_keyring=True):
    """
    Yield an Jira client instance and handle saving credentials to a keyring if there is one.

    User will be prompted for username / password if necessary.
    :param jira_user: The username.
    :type jira_user: str or None.
    :param jira_password:  The password.
    :type jira_password:  str or None.
    :param bool use_keyring: Don't use a keyring even if it is available if this is set to False.
    :yield: Jira client instance.
    """
    keyring_impl = Keyring(KEYRING_SERVICE_NAME)
    initial_credentials = JiraCredentials(jira_user, jira_password)
    try:
        if use_keyring and jira_user is None and jira_password is None:
            initial_credentials = JiraCredentials.decode(keyring_impl.read(KEYRING_PROPERTY_NAME))
        LOG.debug('jira_keyring_helper: input', jira_credentials=initial_credentials)
        jira, used_credentials = new_jira_client(initial_credentials)
        yield jira

    except JIRAError as e:
        if 'CAPTCHA_CHALLENGE' in e.text:
            text = '''Captcha verification has been triggered by
JIRA - please go to JIRA ({}) using your web
browser, log out of JIRA, log back in
entering the captcha; after that is done
please re-run the script'''.format(JIRA_URL)
            LOG.error(text, exc_info=1)
            raise Exception(text)
        raise

    LOG.debug(
        'jira_keyring_helper: context helper cleanup',
        jira_credentials=used_credentials,
        use_keyring=use_keyring,
        credentials_changed=used_credentials != initial_credentials)
    if use_keyring and used_credentials != initial_credentials:
        try:
            keyring_impl.write(KEYRING_PROPERTY_NAME, used_credentials.encode())
        except PasswordSetError as e:
            message = e.message + \
                '''.
You may need to codesign your python executable, refer to signal_processing/README.md.'''
            LOG.error(message, exc_info=1)
            raise PasswordSetError(message)
