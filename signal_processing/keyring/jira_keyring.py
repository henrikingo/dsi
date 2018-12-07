"""
Wrap jira access and keyring support in a context manager.

Usage:

    from signal_processing.jira_helpers import jira_keyring_helper

    with jira_keyring_helper() as etl_jira:
        issue = etl_jira.jira.issue('BF-1234')

The previous code will use a keyring if available or prompt for username / password if no keyring
or no stored credentials.

If the code in the context manager completes without an exception and the credentials have changed
then the keyring data will be updated if it has changed.

"""
from __future__ import print_function

import ast
from contextlib import contextmanager
from keyring.errors import PasswordSetError

from jira.exceptions import JIRAError

from signal_processing.etl_jira_mongo import EtlJira, JIRA_URL
from signal_processing.keyring.keyring_impl import Keyring
import structlog

LOG = structlog.getLogger(__name__)

KEYRING_SERVICE_NAME = 'signal processing'
""" The keyring service name. """

KEYRING_PROPERTY_NAME = 'jira_username_and_password'
""" The keyring property name. """

JIRA_USER = 'jira_user'
""" The jira user key name in the etl jira options. """

JIRA_PASSWORD = 'jira_password'
""" The jira password key name in the etl jira options. """


def redact_password(password):
    """
    Redacted the password.

    :param password: The password to redact.
    :type password: str or None.
    :return: A redacted password.
    """

    if password is not None:
        return '*' * min(8, max(8, len(password)))
    return password


def redact_credentials(credentials):
    """
    Create a Redacted copy of the credentials..

    :param dict credentials: The credentials to redact.
    :return: A shallow copy of credentials dict with password redacted.
    """

    if credentials:
        credentials = credentials.copy()
        if JIRA_PASSWORD in credentials and credentials[JIRA_PASSWORD] is not None:
            credentials[JIRA_PASSWORD] = redact_password(credentials[JIRA_PASSWORD])
    return credentials


def _credentials_changed(username, password, credentials):
    """
    Check if credentials have change.

    :param str username: The username.
    :param str password: The password.
    :param dict credentials: The credentials containing JIRA_USER and JIRA_PASSWORD fields.
    :return: True if something changed.
    """
    return username != credentials[JIRA_USER] or password != credentials[JIRA_PASSWORD]


def _encode_credentials(credentials):
    """
    Encode the JIRA_USER and JIRA_PASSWORD fields.

    :param dict credentials: The credentials containing JIRA_USER and JIRA_PASSWORD fields.
    :return: A string of encoded credentials.
    """
    return '{}'.format([credentials[JIRA_USER], credentials[JIRA_PASSWORD]])


def _decode_credentials(credentials):
    """
    Decode the JIRA_USER and JIRA_PASSWORD fields.

    :param str credentials: The credentials containing JIRA_USER and JIRA_PASSWORD fields.
    :return: A tuple of (username, password).
    """
    if credentials is not None:
        return ast.literal_eval(credentials)
    return None, None


@contextmanager
def jira_keyring(jira_user=None, jira_password=None, use_keyring=True):
    """
    Yield an EtlJira instance and handle saving credentials to a keyring if there is one. EtlJira
    will prompt for username / password if necessary.
    :param jira_user: The username.
    :type jira_user: str or None.
    :param jira_password:  The password.
    :type jira_password:  str or None.
    :param bool use_keyring: Don't use a keyring even if it is available if this is set to False.
    :yield: EtlJira instance.
    """
    etl_jira = None
    keyring_impl = Keyring(KEYRING_SERVICE_NAME)
    username, password = jira_user, jira_password
    try:
        if use_keyring and jira_user is None and jira_password is None:
            username, password = _decode_credentials(keyring_impl.read(KEYRING_PROPERTY_NAME))
        LOG.debug(
            'jira_keyring_helper: input',
            jira_user=username,
            jira_password=redact_password(password))
        etl_jira = EtlJira(dict(jira_user=username, jira_password=password))
        yield etl_jira

        # ensure that the username / password were checked
        _ = etl_jira.jira

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
    except PasswordSetError as e:
        message = e.message + \
                  '''.
You may need to codesign your python executable, refer to signal_processing/README.md.'''

        LOG.error(message, exc_info=1)
        raise PasswordSetError(message)
    else:
        options = etl_jira.options
        LOG.debug(
            'jira_keyring_helper: saving',
            options=redact_credentials(options),
            use_keyring=use_keyring,
            credentials_changed=_credentials_changed(username, password, options))
        if use_keyring and _credentials_changed(username, password, options):
            keyring_impl.write(KEYRING_PROPERTY_NAME, _encode_credentials(options))
