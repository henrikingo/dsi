"""Unit tests for signal_processing/keyring/credentials.py."""

import unittest

from signal_processing.keyring.credentials import Credentials


class TestCredentials(unittest.TestCase):
    """
    Test the Credentials class.
    """

    def test_redact_password_none(self):
        """ Test service name."""
        self.assertIsNone(Credentials._redact_password(None))

    def test_redact_password_short(self):
        """ Test short password."""
        self.assertEqual('********', Credentials._redact_password(''))

    def test_redact_password_long(self):
        """ Test long password."""
        self.assertEqual('********', Credentials._redact_password(' ' * 20))

    def test_str_empty(self):
        """ Test service name."""
        credentials = Credentials(None, None)
        self.assertEqual('(None, None)', str(credentials))

    def test_str_short(self):
        """ Test short password."""
        credentials = Credentials('user', '')
        self.assertEqual('(user, ********)', str(credentials))

    def test_str_long(self):
        """ Test long password."""
        credentials = Credentials('user', ' ' * 20)
        self.assertEqual('(user, ********)', str(credentials))

    def test_eq_self(self):
        """ Test no change."""
        credentials = Credentials(None, None)
        self.assertTrue(credentials, credentials)

    def test_eq_same(self):
        """ Test no change."""
        credentials1 = Credentials(None, None)
        credentials2 = Credentials(None, None)
        self.assertEqual(credentials1, credentials2)
        self.assertEqual(credentials2, credentials1)

    def test_eq_username_change(self):
        """ Test no change."""
        credentials1 = Credentials('user', None)
        credentials2 = Credentials(None, None)
        self.assertNotEqual(credentials1, credentials2)
        self.assertNotEqual(credentials2, credentials1)

    def test_eq_password_change(self):
        """ Test no change."""
        credentials1 = Credentials('user', 'password')
        credentials2 = Credentials('user', None)
        self.assertNotEqual(credentials1, credentials2)
        self.assertNotEqual(credentials2, credentials1)

    def test_encode_none(self):
        """ Test no change."""
        encoded = Credentials(None, None).encode()
        self.assertEquals('[None, None]', encoded)

    def test_encode_username(self):
        """ Test username."""
        encoded = Credentials('username', None).encode()
        self.assertEquals("['username', None]", encoded)

    def test_encode_password(self):
        """ Test password."""
        encoded = Credentials(None, 'password').encode()
        self.assertEquals("[None, 'password']", encoded)

    def test_encode_both(self):
        """ Test password."""
        encoded = Credentials('username', 'password').encode()
        self.assertEquals("['username', 'password']", encoded)

    def test_decode_none(self):
        """ Test no change."""
        decoded = Credentials.decode('[None, None]')
        self.assertEquals(Credentials(None, None), decoded)

    def test_decode_username(self):
        """ Test username."""
        decoded = Credentials.decode("['username', None]")
        self.assertEquals(Credentials('username', None), decoded)

    def test_decode_password(self):
        """ Test password."""
        decoded = Credentials.decode("[None, 'password']")
        self.assertEquals(Credentials(None, 'password'), decoded)

    def test_decoded_both(self):
        """ Test password."""
        decoded = Credentials.decode("['username', 'password']")
        self.assertEquals(Credentials('username', 'password'), decoded)
