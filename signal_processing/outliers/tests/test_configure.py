"""
Unit tests for signal_processing/outliers/evaluate.py.
"""
from __future__ import print_function

import re
import unittest

from mock import MagicMock, patch

from signal_processing.model.configuration import DEFAULT_CONFIG
from signal_processing.outliers.configure import view_configuration, set_configuration, \
    delete_configuration, stream_human_readable, unset_configuration, sanitize, \
    to_test_identifier, empty
from signal_processing.tests.helpers import Helpers

NS = 'signal_processing.outliers.configure'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestSanitize(unittest.TestCase):
    """ Test sanitize. """

    def test_basic(self):
        """ test sanitize with basic types. """
        for value in ['string', 1, 1.0, ['string', 1, 1.0]]:
            self.assertEquals(value, sanitize(value))

    def test_regex(self):
        """ test sanitize with regexes. """
        patterns = [('^test$', 0, ''),
                    ('^test$', re.IGNORECASE | re.MULTILINE | re.VERBOSE | re.DOTALL, 'imxs')]
        for pattern, flag_value, flags in patterns:
            regex = re.compile(pattern, flags=flag_value)
            self.assertEquals('/{}/{}'.format(pattern, flags), sanitize(regex))

    def test_list_regex(self):
        """ test sanitize with list of regexes. """
        pattern = '^test$'
        value = [1, 2, re.compile(pattern)]
        self.assertEquals([1, 2, '/{}/'.format(pattern)], sanitize(value))

    def test_dict_regex(self):
        """ test sanitize with dict of regexes. """
        pattern = '^test$'
        value = {'first': 1, 'second': 2, 'pattern': re.compile(pattern)}
        self.assertDictEqual({
            'first': 1,
            'second': 2,
            'pattern': '/{}/'.format(pattern)
        }, sanitize(value))


class TestToTestIdentifier(unittest.TestCase):
    """ Test to_test_identifier. """

    def _test(self, to_key=None):
        test_identifier = Helpers.create_test_identifier()
        keys = ['project', 'variant', 'task', 'test', 'thread_level']
        if to_key is not None:
            pos = keys.index(to_key) + 1
            keep = keys[:pos]
            remove = keys[pos:]
        else:
            keep = keys
            remove = []

        for key in remove:
            del test_identifier[key]
        self.assertListEqual([test_identifier[key] for key in keep],
                             to_test_identifier(test_identifier))

    def test_full(self):
        """ to_test_identifier with full data. """
        self._test()

    def test_to_testname(self):
        """ to_test_identifier to test. """
        self._test(to_key='test')

    def test_to_task(self):
        """ to_test_identifier to task. """
        self._test(to_key='task')

    def test_to_variant(self):
        """ to_test_identifier to variant. """
        self._test(to_key='variant')

    def test_to_project(self):
        """ to_test_identifier to project. """
        self._test(to_key='project')


class TestEmpty(unittest.TestCase):
    """ Test to_test_identifier. """

    def test_empty_list(self):
        """ test empty with []. """
        self.assertEquals('EMPTY', empty([]))

    def test_list_with_none(self):
        """ test empty with []. """
        self.assertEquals('EMPTY', empty([None]))

    def test_list_with_none_false(self):
        """ test empty with []. """
        value = [None, False]
        self.assertEquals(value, empty(value))

    def test_empty_dict(self):
        """ test empty with {}. """
        self.assertEquals('EMPTY', empty({}))

    def test_dict_with_none(self):
        """ test empty with {}. """
        self.assertEquals('EMPTY', empty({'key': None}))

    def test_dict_with_none_false(self):
        """ test empty with {}. """
        value = {'key': None, 'key1': False}
        self.assertEquals(value, empty(value))

    def test_str(self):
        """ test empty with {}. """
        self.assertEquals('value', empty('value'))


class TestVewConfiguration(unittest.TestCase):
    """ Test view_configuration. """

    # pylint: disable=no-self-use
    def _test(self, cursor=False):
        mock_model = MagicMock(name='model', collection='collection')
        layers = [] if not cursor else ['configuration']
        mock_model.get_configuration.return_value = layers
        mock_command_config = MagicMock(name='command_config')
        test_identifier = {'project': 'sys-perf'}

        with patch(ns('ConfigurationModel'), return_value=mock_model),\
             patch(ns('OutlierConfiguration')) as mock_outlier_config,\
             patch(ns('combine_outlier_configs')) as mock_combine,\
             patch(ns('stream_human_readable')) as mock_stream:
            mock_combine.return_value = DEFAULT_CONFIG
            view_configuration(test_identifier, mock_command_config)
        mock_combine.assert_called_once_with(test_identifier, layers,
                                             mock_outlier_config.return_value)

        mock_stream.assert_called_once_with(test_identifier, mock_combine.return_value,
                                            mock_model.collection, DEFAULT_CONFIG, layers,
                                            mock_outlier_config.return_value)

    def test_empty(self):
        """ test with no data. """
        self._test()

    def test_config(self):
        """ test with data. """
        self._test(cursor=True)


class TestSetConfiguration(unittest.TestCase):
    """ Test set_configuration. """

    # pylint: disable=no-self-use
    def test(self):
        """ test set_configuration. """
        mock_model = MagicMock(name='model', collection='collection')
        mock_command_config = MagicMock(name='command_config')
        test_identifier = {'project': 'sys-perf'}
        configuration = {}
        with patch(ns('ConfigurationModel'), return_value=mock_model):
            set_configuration(test_identifier, configuration, mock_command_config)

        mock_model.set_configuration.assert_called_once_with(test_identifier, configuration)


class TestUnsetConfiguration(unittest.TestCase):
    """ Test unset_configuration. """

    # pylint: disable=no-self-use
    def test(self):
        """ test unset_configuration. """
        mock_model = MagicMock(name='model', collection='collection')
        mock_command_config = MagicMock(name='command_config')
        test_identifier = {'project': 'sys-perf'}
        configuration = {}
        with patch(ns('ConfigurationModel'), return_value=mock_model):
            unset_configuration(test_identifier, configuration, mock_command_config)

        mock_model.unset_configuration.assert_called_once_with(test_identifier, configuration)


class TestDeleteConfiguration(unittest.TestCase):
    """ Test delete_configuration. """

    # pylint: disable=no-self-use
    def test(self):
        """ test delete_configuration. """
        mock_model = MagicMock(name='model', collection='collection')
        mock_command_config = MagicMock(name='command_config')
        test_identifier = {'project': 'sys-perf'}
        with patch(ns('ConfigurationModel'), return_value=mock_model):
            delete_configuration(test_identifier, mock_command_config)

        mock_model.delete_configuration.assert_called_once_with(test_identifier)


class TestStreamHumanReadable(unittest.TestCase):
    """ Test stream_human_readable. """

    # pylint: disable=no-self-use
    def test_stream_human_readable(self):
        """ test stream_human_readable. """

        test_identifier = Helpers.create_test_identifier()
        default_config = MagicMock(name='default config')
        layers = MagicMock(name='layers')
        override_config = MagicMock(name='override config')
        width = 26
        with patch(ns('HUMAN_READABLE_TEMPLATE')) as mock_stream:
            configuration = DEFAULT_CONFIG
            collection = 'the collection'
            mock_collection = MagicMock(name='collection', collection=collection)
            stream_human_readable(test_identifier, configuration, mock_collection, default_config,
                                  layers, override_config)
            mock_stream.stream.assert_called_once_with(
                _id=test_identifier,
                configuration=configuration._asdict(),
                collection=mock_collection,
                test_identifier=test_identifier,
                default_config=default_config._asdict(),
                layers=layers,
                override_config=override_config._asdict(),
                min_width=width)
