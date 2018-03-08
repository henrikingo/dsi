#!/usr/bin/env python2.7
"""Tests for the mongodb_setup_helpers module"""

import exceptions
import unittest

import common.mongodb_setup_helpers

#pylint: disable=invalid-name


class TestHelperFunctions(unittest.TestCase):
    """Basic tests for helper functions in mongodb_setup"""

    def test_merge_dicts(self):
        """Test merge_dicts correctly overrides literals."""
        base = {'a': 1, 'b': 'string'}
        override = {'b': 2, 'c': 3}
        expected_merge = {'a': 1, 'b': 2, 'c': 3}
        self.assertEqual(common.mongodb_setup_helpers.merge_dicts(base, override), expected_merge)

    def test_merge_dicts_nested(self):
        """Test merge_dicts correctly overrides dictionaries."""
        base = {'a': 1, 'b': 'string', 'setParameters': {'a': 1, 'b': 'string'}}
        override = {'b': 2, 'c': 3, 'setParameters': {'b': 2, 'c': 3}}
        expected_merge = {'a': 1, 'b': 2, 'c': 3, 'setParameters': {'a': 1, 'b': 2, 'c': 3}}
        self.assertEqual(common.mongodb_setup_helpers.merge_dicts(base, override), expected_merge)

    def test_mongodb_auth_configured_true(self):
        """
        Test mongodb_auth_configured with auth settings supplied.
        """
        config = {
            'bootstrap': {
                'authentication': 'enabled'
            },
            'mongodb_setup': {
                'authentication': {
                    'enabled': {
                        'username': 'username',
                        'password': 'password'
                    }
                }
            }
        }
        self.assertTrue(common.mongodb_setup_helpers.mongodb_auth_configured(config))

    def test_mongodb_auth_configured_false(self):
        """
        Test mongodb_auth_configured with not auth settings supplied.
        """
        config = {'bootstrap': {'authentication': 'disabled'}}
        self.assertFalse(common.mongodb_setup_helpers.mongodb_auth_configured(config))

    def test_auth_configured_throws(self):
        """
        Test mongodb_auth_configured with incomplete auth settings.
        """
        config = {
            'bootstrap': {
                'authentication': 'enabled'
            },
            'mongodb_setup': {
                'authentication': {
                    'enabled': {
                        'username': 'username'
                    }
                }
            }
        }
        with self.assertRaises(exceptions.AssertionError):
            common.mongodb_setup_helpers.mongodb_auth_configured(config)

    def test_mongodb_auth_settings_enabled(self):
        """
        Test mongodb_auth_settings_enbaled with auth settings supplied.
        """
        config = {
            'bootstrap': {
                'authentication': 'enabled'
            },
            'mongodb_setup': {
                'authentication': {
                    'enabled': {
                        'username': 'username',
                        'password': 'password'
                    }
                }
            }
        }
        self.assertEqual(
            common.mongodb_setup_helpers.mongodb_auth_settings(config),
            common.mongodb_setup_helpers.MongoDBAuthSettings('username', 'password'))

    def test_mongodb_auth_settings_missing(self):
        """
        Test mongodb_auth_settings_enbaled with auth settings supplied.
        """
        config = {'bootstrap': {'authentication': 'disabled'}}
        self.assertEqual(common.mongodb_setup_helpers.mongodb_auth_settings(config), None)
