"""
Unit tests for signal_processing/commands/attach.py.
"""

import unittest

from mock import patch

from signal_processing.keyring.keyring_impl import NoopKeyring, Keyring


class TestNoopKeyring(unittest.TestCase):
    """
    Test NoopKeyring.
    """

    def setUp(self):
        self.service_name = 'service'
        self.keyring = NoopKeyring(self.service_name)

    def test_service_name(self):
        """ Test service name."""
        self.assertEquals(self.service_name, self.keyring.service_name)

    def test_read(self):
        """ Test read."""
        self.assertIsNone(self.keyring.read('name'))

    def test_write(self):
        """ Test write."""
        self.keyring.write('name', 'value ')


class TestKeyring(unittest.TestCase):
    """
    Test Keyring.
    """

    def setUp(self):
        self.service_name = 'service'
        self.keyring = Keyring(self.service_name)

    def test_service_name(self):
        """ Test service name."""
        self.assertEquals(self.service_name, self.keyring.service_name)

    def test_read(self):
        """ Test read."""
        with patch('signal_processing.keyring.keyring_impl.keyring', create=True) as mock_keyring:
            password = 'password'
            property_name = 'name'
            mock_keyring.get_password.return_value = password
            self.assertEquals(password, self.keyring.read(property_name))
            mock_keyring.get_password.assert_called_once_with(self.service_name, property_name)

    def test_write(self):
        """ Test write."""
        with patch('signal_processing.keyring.keyring_impl.keyring', create=True) as mock_keyring:
            password = 'password'
            property_name = 'name'
            self.keyring.write(property_name, password)
            mock_keyring.set_password.assert_called_once_with(self.service_name, property_name,
                                                              password)
