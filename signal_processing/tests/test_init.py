"""
Unit tests for signal_processing/commands/change_points/init.py.
"""

import unittest

from click.testing import CliRunner
from mock import patch
import yaml

from signal_processing.keyring.credentials import Credentials
from signal_processing.commands.change_points.init import write_configuration, \
    validate_mongo_connection, init_command


def read_config_file(filename):
    with open(filename) as input_file:
        return yaml.load(input_file.read())


class TestInitCommand(unittest.TestCase):
    @patch('signal_processing.commands.change_points.init.open')
    def test_write_configuration_that_exists(self, open_mock):
        write_configuration({}, 'destination')
        open_mock.return_value.__enter__.return_value.write.assert_called()

    @patch('signal_processing.commands.change_points.init.new_mongo_client')
    def test_mongo_connection_calls_mongo_keyring(self, new_mongo_client_mock):
        validate_mongo_connection('mongodb://mongo_uri', Credentials('user', 'pass'))
        new_mongo_client_mock.assert_called()

    @patch('signal_processing.commands.change_points.init.os.path.exists')
    def test_init_with_no_auth(self, exists_mock):
        inputs = [
            'logfile',  # logfile to use.
            'mongodb://host',  # mongo uri.
            'n',  # is auth required?
            ''
        ]
        target_file = 'test.yml'
        exists_mock.return_value = False
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                init_command, ['--target-file', target_file], input='\n'.join(inputs))

            self.assertEqual(0, result.exit_code)

            config = read_config_file(target_file)
            self.assertEqual(inputs[0], config['logfile'])
            self.assertEqual(inputs[1], config['mongo_uri'])
            self.assertNotIn('auth_mode', config)

    @patch('signal_processing.commands.change_points.init.os.path.exists')
    def test_init_with_prompts(self, exists_mock):
        inputs = [
            'logfile',  # logfile to use.
            'mongodb://host',  # mongo uri.
            'y',  # Is auth required?
            'n',  # Should keyring be used?
            ''
        ]
        target_file = 'test.yml'
        exists_mock.return_value = False
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                init_command, ['--target-file', target_file], input='\n'.join(inputs))

            self.assertEqual(0, result.exit_code)

            config = read_config_file(target_file)
            self.assertEqual(inputs[0], config['logfile'])
            self.assertEqual(inputs[1], config['mongo_uri'])
            self.assertEqual('prompt', config['auth_mode'])
