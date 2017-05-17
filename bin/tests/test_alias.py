"""Tests for bin/alias.py"""
# pylint: disable=wrong-import-position

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alias import unalias, expand, ALIASES


class AliasTestCase(unittest.TestCase):
    """Unit tests for Alias utility functions."""

    def setUp(self):
        """Create the objects required for this set of tests"""
        self.config = {'infrastructure_provisioning':
                           {'tfvars':
                                {'ssh_user': 'ec2-user', 'ssh_key_file': '../../aws.pem'},
                            'out':
                                {'mongod': [
                                    {'public_ip': '10.2.3.4', 'private_ip': '10.0.0.1'},
                                    {'public_ip': '10.2.3.5', 'private_ip': '10.0.0.2'},
                                    {'public_ip': '10.2.3.6', 'private_ip': '10.0.0.3'},
                                    {'public_ip': '10.2.3.7', 'private_ip': '10.0.0.4'},
                                    {'public_ip': '10.2.3.8', 'private_ip': '10.0.0.5'}],
                                 'mongos': [
                                     {'public_ip': '10.2.3.9', 'private_ip': '10.0.0.6'},
                                     {'public_ip': '10.2.3.10', 'private_ip': '10.0.0.7'},
                                     {'public_ip': '10.2.3.11', 'private_ip': '10.0.0.8'}],
                                 'configsvr': [
                                     {'public_ip': '10.2.3.12', 'private_ip': '10.0.0.9'},
                                     {'public_ip': '10.2.3.13', 'private_ip': '10.0.0.10'},
                                     {'public_ip': '10.2.3.14', 'private_ip': '10.0.0.11'}],
                                 'workload_client': [
                                     {'public_ip': '10.2.3.15', 'private_ip': '10.0.0.12'}]
                                }
                           },
                       'runtime': {'mongodb_binary_archive': 'http://foo.tgz'}
                      }

    def test_unalias(self):
        """check that the alias work as expected."""

        self.assertEquals(unalias('md'), 'mongod')
        self.assertEquals(unalias('ms'), 'mongos')
        self.assertEquals(unalias('cs'), 'configsvr')
        self.assertEquals(unalias('configsrv'), 'configsvr')
        self.assertEquals(unalias('wc'), 'workload_client')

        self.assertEquals(unalias('MD'), 'MD')

        aliases = {'MD': 'MONGOD', 'md': 'mongod'}
        self.assertEquals(unalias('MD', aliases), 'MONGOD')
        self.assertEquals(unalias('md', aliases), 'mongod')

        # do not do something like the following, as it will permanently add to
        # ALIASES, either copy before the update or use a dict constructor as shown
        # in the test
        #
        # aliases = ALIASES.update({'m': 'mongod'})
        aliases = dict(ALIASES, **{'m': 'mongod'})
        self.assertEquals(unalias('m', aliases), 'mongod')
        self.assertEquals(unalias('md', aliases), 'mongod')

        overrides = dict(ALIASES, **{'m': 'mongod', 'md': 'MONGOD'})
        self.assertEquals(unalias('m', overrides), 'mongod')
        self.assertEquals(unalias('md', overrides), 'MONGOD')

    def test_expand(self):
        """check that the expand works as expected."""
        self.assertEquals(expand('md'), 'md.0.public_ip')
        self.assertEquals(expand('mongod'), 'mongod.0.public_ip')
        self.assertEquals(expand('mongod.0'), 'mongod.0.public_ip')

    def test_expand_ex(self):
        """check that the expand throws exceptions as expected."""
        self.assertRaisesRegexp(ValueError, 'The max level of nesting is 3:', expand,
                                'md.0.public_ip.extra')

    def test_expand_and_unalias(self):
        """check that the order of alias and expand is not important."""
        # runtime = self.config['runtime']
        self.assertEquals(expand(unalias('md')), 'mongod.0.public_ip')
        self.assertEquals(unalias(expand('md')), expand(unalias('md')))

if __name__ == '__main__':
    unittest.main()
