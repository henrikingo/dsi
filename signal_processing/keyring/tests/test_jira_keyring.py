"""
Unit tests for signal_processing/commands/attach.py.
"""

import unittest

from mock import patch, MagicMock

from signal_processing.keyring.jira_keyring import redact_password, redact_credentials, \
    JIRA_PASSWORD, _credentials_changed, JIRA_USER, _encode_credentials, _decode_credentials, \
    jira_keyring, KEYRING_PROPERTY_NAME
from jira.exceptions import JIRAError

try:
    from keyring.errors import PasswordSetError
    KEYRING_IMPORT_FAILS = False
except ImportError:
    KEYRING_IMPORT_FAILS = True


class TestRedactPassword(unittest.TestCase):
    """
    Test redact_password.
    """

    def test_none(self):
        """ Test service name."""
        self.assertIsNone(redact_password(None))

    def test_short(self):
        """ Test short password."""
        self.assertEquals('********', redact_password(''))

    def test_long(self):
        """ Test long password."""
        self.assertEquals('********', redact_password(' ' * 20))


class TestRedactCredentials(unittest.TestCase):
    """
    Test redact_credentials.
    """

    def test_none(self):
        """ Test service name."""
        self.assertIsNone(redact_credentials(None))

    def test_empty(self):
        """ Test service name."""
        self.assertEquals({}, redact_credentials({}))

    def test_short(self):
        """ Test short password."""
        self.assertEquals({JIRA_PASSWORD: '********'}, redact_credentials({JIRA_PASSWORD: ''}))

    def test_long(self):
        """ Test long password."""
        self.assertEquals({
            JIRA_PASSWORD: '********'
        }, redact_credentials({
            JIRA_PASSWORD: ' ' * 20
        }))

    def test_other(self):
        """ Test other."""
        self.assertEquals({'other': 'value'}, redact_credentials({'other': 'value'}))

    def test_password_other(self):
        """ Test long password."""
        self.assertEquals({
            'other': 'value',
            JIRA_PASSWORD: '********'
        }, redact_credentials({
            'other': 'value',
            JIRA_PASSWORD: ''
        }))


class TestCredentialsChanged(unittest.TestCase):
    """
    Test _credentials_changed.
    """

    def test_no_change(self):
        """ Test no change."""
        self.assertFalse(_credentials_changed(None, None, {JIRA_PASSWORD: None, JIRA_USER: None}))

    def test_username_change(self):
        """ Test no change."""
        self.assertTrue(
            _credentials_changed('username', None, {
                JIRA_USER: None,
                JIRA_PASSWORD: None
            }))

    def test_password_change(self):
        """ Test no change."""
        self.assertTrue(
            _credentials_changed(None, 'password', {
                JIRA_USER: None,
                JIRA_PASSWORD: None
            }))


class TestEncodeCredentials(unittest.TestCase):
    """
    Test _encode_credentials.
    """

    def test_none(self):
        """ Test no change."""
        self.assertEquals('[None, None]', _encode_credentials({
            JIRA_PASSWORD: None,
            JIRA_USER: None
        }))

    def test_username(self):
        """ Test username."""
        self.assertEquals("['username', None]",
                          _encode_credentials({
                              JIRA_USER: 'username',
                              JIRA_PASSWORD: None
                          }))

    def test_password(self):
        """ Test password."""
        self.assertEquals("[None, 'password']",
                          _encode_credentials({
                              JIRA_USER: None,
                              JIRA_PASSWORD: 'password'
                          }))

    def test_both(self):
        """ Test password."""
        self.assertEquals("['username', 'password']",
                          _encode_credentials({
                              JIRA_USER: 'username',
                              JIRA_PASSWORD: 'password'
                          }))


class TestDecodeCredentials(unittest.TestCase):
    """
    Test _decode_credentials.
    """

    def test_none(self):
        """ Test no change."""
        self.assertEquals([None, None], _decode_credentials('[None, None]'))

    def test_username(self):
        """ Test username."""
        self.assertEquals(['username', None], _decode_credentials("['username', None]"))

    def test_password(self):
        """ Test password."""
        self.assertEquals([None, 'password'], _decode_credentials("[None, 'password']"))

    def test_both(self):
        """ Test password."""
        self.assertEquals(['username', 'password'], _decode_credentials("['username', 'password']"))


class TestJiraKeyring(unittest.TestCase):
    """
    Test jira_keyring.
    """

    def setUp(self):
        """
        patch keyring, keyring.errors imports when no implementation is available.
        """

        if KEYRING_IMPORT_FAILS:
            modules = {
                'keyring': MagicMock(name='keyring'),
                'keyring.errors': MagicMock(name='keyring.errors')
            }
            self.module_patcher = patch.dict('sys.modules', modules)
            self.module_patcher.start()

    def tearDown(self):
        """
        clean up keyring, keyring.errors imports.
        """

        if KEYRING_IMPORT_FAILS:
            self.module_patcher.stop()

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
                 patch('signal_processing.keyring.jira_keyring._decode_credentials',
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
                 patch('signal_processing.keyring.jira_keyring._decode_credentials',
                       return_value=['username', 'password']),\
                 patch('signal_processing.keyring.jira_keyring.EtlJira',
                       side_effect=Exception('boom')) as mock_etl_jira:
                with jira_keyring():
                    pass
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_etl_jira.assert_called_once_with(dict(jira_user='username', jira_password='password'))
        self.assertIn('boom', context.exception)

    def test_jira_exception_in_jira(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        with self.assertRaises(JIRAError) as context:
            with patch('signal_processing.keyring.jira_keyring.Keyring',
                       return_value=mock_keyring),\
                 patch('signal_processing.keyring.jira_keyring._decode_credentials',
                       return_value=['username', 'password']),\
                 patch('signal_processing.keyring.jira_keyring.EtlJira',
                       side_effect=JIRAError(text='boom')) as mock_etl_jira:
                with jira_keyring():
                    pass
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_etl_jira.assert_called_once_with(dict(jira_user='username', jira_password='password'))
        self.assertIn('boom', context.exception.text)

    def test_captcha_exception(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        with self.assertRaises(Exception) as context:
            with patch('signal_processing.keyring.jira_keyring.Keyring',
                       return_value=mock_keyring),\
                 patch('signal_processing.keyring.jira_keyring._decode_credentials',
                       return_value=['username', 'password']),\
                 patch('signal_processing.keyring.jira_keyring.EtlJira',
                       side_effect=JIRAError(text='CAPTCHA_CHALLENGE')) as mock_etl_jira:
                with jira_keyring():
                    pass
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_etl_jira.assert_called_once_with(dict(jira_user='username', jira_password='password'))
        self.assertIn('Captcha verification has been triggered by', str(context.exception))

    @unittest.skipIf(KEYRING_IMPORT_FAILS, 'no keyring implmenetation')
    def test_codesign_exception(self):
        """ Test mac specific code sign issue exception."""

        mock_keyring = MagicMock(name='keyring')
        with self.assertRaises(PasswordSetError) as context:
            with patch('signal_processing.keyring.jira_keyring.Keyring',
                       return_value=mock_keyring),\
                 patch('signal_processing.keyring.jira_keyring._decode_credentials',
                       return_value=['username', 'password']),\
                 patch('signal_processing.keyring.jira_keyring.EtlJira',
                       side_effect=PasswordSetError("Can't store password on keychain")) as mock_etl_jira:
                with jira_keyring():
                    pass
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_etl_jira.assert_called_once_with(dict(jira_user='username', jira_password='password'))
        self.assertIn('Can\'t store password on keychain', str(context.exception))
        self.assertIn('refer to signal_processing/README.md', str(context.exception))

    def test_dont_use_keyring(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        with patch('signal_processing.keyring.jira_keyring.Keyring', return_value=mock_keyring),\
             patch('signal_processing.keyring.jira_keyring._decode_credentials',
                   return_value=['username', 'password']),\
             patch('signal_processing.keyring.jira_keyring.EtlJira') as mock_etl_jira:
            with jira_keyring(use_keyring=False):
                pass

        mock_etl_jira.assert_called_once_with(dict(jira_user=None, jira_password=None))

        mock_keyring.read.assert_not_called()
        mock_keyring.write.assert_not_called()

    def test_write_with_no_credentials(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        mock_etl_jira_instance = MagicMock(name='mock_etl_jira_instance')
        options = dict(jira_user='username', jira_password='password')
        mock_jira = MagicMock(name='jira')
        with patch('signal_processing.keyring.jira_keyring.Keyring',
                   return_value=mock_keyring), \
             patch('signal_processing.keyring.jira_keyring._decode_credentials',
                   return_value=[None, None]),\
             patch('signal_processing.keyring.jira_keyring.EtlJira', autospec=True)\
                as mock_etl_jira:
            mock_etl_jira.return_value = mock_etl_jira_instance
            mock_etl_jira.jira.return_value = mock_jira
            mock_etl_jira_instance.options = options
            with jira_keyring(jira_password='password'):
                pass

        mock_etl_jira.assert_called_once_with(dict(jira_user=None, jira_password='password'))
        mock_keyring.read.assert_not_called()
        mock_keyring.write.assert_called_once_with(KEYRING_PROPERTY_NAME,
                                                   "['username', 'password']")

    def test_write_credentials(self):
        """ Test exception."""

        mock_keyring = MagicMock(name='keyring')
        mock_etl_jira_instance = MagicMock(name='mock_etl_jira_instance')
        options = dict(jira_user='username', jira_password='password')
        mock_jira = MagicMock(name='jira')
        with patch('signal_processing.keyring.jira_keyring.Keyring',
                   return_value=mock_keyring), \
             patch('signal_processing.keyring.jira_keyring._decode_credentials',
                   return_value=[None, None]),\
             patch('signal_processing.keyring.jira_keyring.EtlJira', autospec=True)\
                as mock_etl_jira:
            mock_etl_jira.return_value = mock_etl_jira_instance
            mock_etl_jira.jira.return_value = mock_jira
            mock_etl_jira_instance.options = options
            with jira_keyring():
                pass

        mock_etl_jira.assert_called_once_with(dict(jira_user=None, jira_password=None))
        mock_keyring.read.assert_called_once_with(KEYRING_PROPERTY_NAME)
        mock_keyring.write.assert_called_once_with(KEYRING_PROPERTY_NAME,
                                                   "['username', 'password']")
