"""
Unit tests for signal_processing/commands/attach.py.
"""

import unittest

from mock import patch, MagicMock

from jira.exceptions import JIRAError
from keyring.errors import PasswordSetError

from signal_processing.etl_jira_mongo import JiraCredentials
from signal_processing.keyring.jira_keyring import jira_keyring, KEYRING_PROPERTY_NAME


class TestJiraKeyring(unittest.TestCase):
    """
    Test jira_keyring.
    """

    # pylint: disable=no-self-use
    def test_exception_in_keyring(self):
        """ Test exception."""

        with self.assertRaises(Exception) as context:
            # yapf: disable
            with patch('signal_processing.keyring.jira_keyring.Keyring',
                       side_effect=Exception('boom')):
                # yapf: enable
                with jira_keyring():
                    pass
        self.assertIn('boom', context.exception)

    def test_exception_in_decode(self):
        """ Test exception."""

        username_and_password = "['username', 'password']"
        mock_keyring = MagicMock(name='keyring')
        mock_keyring.read.return_value = username_and_password
        with self.assertRaises(Exception) as context:
            with patch('signal_processing.keyring.jira_keyring.Keyring',
                       return_value=mock_keyring), \
                patch('signal_processing.keyring.jira_keyring.JiraCredentials.decode',
                      side_effect=Exception('boom')) as mock_decode_credentials:
                with jira_keyring():
                    pass
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_decode_credentials.assert_called_once_with(username_and_password)
        self.assertIn('boom', context.exception)

    def test_exception_in_jira(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        with self.assertRaises(Exception) as context:
            with patch('signal_processing.keyring.jira_keyring.Keyring',
                       return_value=mock_keyring),\
                patch('signal_processing.keyring.jira_keyring.JiraCredentials.decode',
                      return_value=JiraCredentials('username', 'password')),\
                patch('signal_processing.keyring.jira_keyring.new_jira_client',
                      side_effect=Exception('boom')) as mock_new_jira_client:
                with jira_keyring():
                    pass
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_new_jira_client.assert_called_once_with(JiraCredentials('username', 'password'))
        self.assertIn('boom', context.exception)

    def test_jira_exception_in_jira(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        with self.assertRaises(JIRAError) as context:
            with patch('signal_processing.keyring.jira_keyring.Keyring',
                       return_value=mock_keyring),\
                patch('signal_processing.keyring.jira_keyring.JiraCredentials.decode',
                      return_value=JiraCredentials('username', 'password')),\
                patch('signal_processing.keyring.jira_keyring.new_jira_client',
                      side_effect=JIRAError(text='boom')) as mock_new_jira_client:
                with jira_keyring():
                    pass
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_new_jira_client.assert_called_once_with(JiraCredentials('username', 'password'))
        self.assertIn('boom', context.exception.text)

    def test_captcha_exception(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        with self.assertRaises(Exception) as context:
            with patch('signal_processing.keyring.jira_keyring.Keyring',
                       return_value=mock_keyring),\
                patch('signal_processing.keyring.jira_keyring.JiraCredentials.decode',
                      return_value=JiraCredentials('username', 'password')),\
                patch('signal_processing.keyring.jira_keyring.new_jira_client',
                      side_effect=JIRAError(text='CAPTCHA_CHALLENGE')) as mock_new_jira_client:
                with jira_keyring():
                    pass
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_new_jira_client.assert_called_once_with(JiraCredentials('username', 'password'))
        self.assertIn('Captcha verification has been triggered by', str(context.exception))

    def test_codesign_exception(self):
        """ Test mac specific code sign issue exception."""

        mock_keyring = MagicMock(name='keyring')
        mock_keyring.write.side_effect = PasswordSetError("Can't store password on keychain")
        with self.assertRaises(PasswordSetError) as context:
            with patch('signal_processing.keyring.jira_keyring.Keyring',
                       return_value=mock_keyring),\
                patch('signal_processing.keyring.jira_keyring.JiraCredentials.decode',
                      return_value=JiraCredentials('username', 'password')),\
                patch('signal_processing.keyring.jira_keyring.new_jira_client') as \
                    mock_new_jira_client:
                mock_new_jira_client.return_value = MagicMock(), JiraCredentials(None, None)
                with jira_keyring():
                    pass
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_new_jira_client.assert_called_once_with(JiraCredentials('username', 'password'))
        self.assertIn('Can\'t store password on keychain', str(context.exception))
        self.assertIn('refer to signal_processing/README.md', str(context.exception))

    def test_dont_use_keyring(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        with patch('signal_processing.keyring.jira_keyring.Keyring', return_value=mock_keyring),\
            patch('signal_processing.keyring.jira_keyring.JiraCredentials.decode',
                  return_value=JiraCredentials('username', 'password')),\
            patch('signal_processing.keyring.jira_keyring.new_jira_client') as \
                mock_new_jira_client:
            mock_new_jira_client.return_value = MagicMock(), JiraCredentials(None, None)
            with jira_keyring(use_keyring=False):
                pass

        mock_new_jira_client.assert_called_once_with(JiraCredentials(None, None))

        mock_keyring.read.assert_not_called()
        mock_keyring.write.assert_not_called()

    def test_write_with_no_credentials(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        mock_jira = MagicMock(name='jira')
        credentials = JiraCredentials('username', 'password')
        with patch('signal_processing.keyring.jira_keyring.Keyring',
                   return_value=mock_keyring), \
            patch('signal_processing.keyring.jira_keyring.JiraCredentials.decode',
                  return_value=JiraCredentials(None, None)),\
            patch('signal_processing.keyring.jira_keyring.new_jira_client')\
                as mock_new_jira_client:
            mock_new_jira_client.return_value = mock_jira, credentials
            with jira_keyring(jira_password='password'):
                pass

        mock_new_jira_client.assert_called_once_with(JiraCredentials(None, 'password'))
        mock_keyring.read.assert_not_called()
        mock_keyring.write.assert_called_once_with(KEYRING_PROPERTY_NAME,
                                                   "['username', 'password']")

    def test_write_credentials(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        mock_jira = MagicMock(name='jira')
        credentials = JiraCredentials('username', 'password')
        with patch('signal_processing.keyring.jira_keyring.Keyring',
                   return_value=mock_keyring), \
            patch('signal_processing.keyring.jira_keyring.JiraCredentials.decode',
                  return_value=JiraCredentials(None, None)),\
            patch('signal_processing.keyring.jira_keyring.new_jira_client')\
                as mock_new_jira_client:
            mock_new_jira_client.return_value = mock_jira, credentials
            with jira_keyring():
                pass

        mock_new_jira_client.assert_called_once_with(JiraCredentials(None, None))
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_keyring.write.assert_called_once_with(KEYRING_PROPERTY_NAME,
                                                   "['username', 'password']")
