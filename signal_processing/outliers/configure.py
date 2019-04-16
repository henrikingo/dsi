"""
Control outlier detection configuration.
"""
from __future__ import print_function

import re
import sys
from collections import MutableMapping
from datetime import datetime
import jinja2

import bson
import structlog
from nose.tools import nottest

from signal_processing.model.configuration import ConfigurationModel, combine_outlier_configs, \
    OutlierConfiguration, DEFAULT_CONFIG

LOG = structlog.getLogger(__name__)
REGEX_TYPE = type(re.compile(''))


def sanitize(obj):
    """
    Jinja2 helper to get a friendly version of an obj.

    :param object obj: The data.
    :return: A string.
    """
    if isinstance(obj, MutableMapping):
        return {k: sanitize(v) for k, v in obj.iteritems()}
    elif isinstance(obj, list):
        return [sanitize(o) for o in obj]
    elif isinstance(obj, (REGEX_TYPE, bson.regex.Regex)):
        flags = ''
        if obj.flags and re.IGNORECASE:
            flags += 'i'
        if obj.flags and re.MULTILINE:
            flags += 'm'
        if obj.flags and re.VERBOSE:
            flags += 'x'
        if obj.flags and re.DOTALL:
            flags += 's'
        return '/{}/{}'.format(obj.pattern, flags)
    return obj


@nottest
def to_test_identifier(obj=None):
    """
    Jinja2 helper to get a friendly version of test identifier values.

    :param object obj: The data.
    :return: A string.
    """

    # if obj is None:
    #     return ''
    return [
        obj[name] for name in ['project', 'variant', 'task', 'test', 'thread_level'] if name in obj
    ]


def empty(obj):
    """
    Jinja2 helper to get a friendly version of a test identifier.

    :param object obj: The data.
    :return: A string.
    """

    if isinstance(obj, MutableMapping):
        return 'EMPTY' if all(v is None for v in obj.values()) else obj
    elif isinstance(obj, list):
        return 'EMPTY' if all(v is None for v in obj) else obj
    return obj


HUMAN_READABLE_TEMPLATE_STR = '''
## {{ collection.name|replace("_", " ")|title}}
## Task: `{{ _id.project }} {{ _id.variant }} {{ _id.task }} {{ _id.test}} {{ _id.thread_level }}`
## {{ 'default'.ljust(min_width) }} : {{ default_config | sanitize }}
{% for layer in layers -%}
## {{ layer | test_identifier | join('/') }} : {{ layer['configuration'] | sanitize }}
{% endfor -%}
## {{ 'override'.ljust(min_width) }} : {{ override_config | empty| sanitize }}

[ {{ now() }} ] Running: `{{ command_line }}`
{% for key, value in configuration.iteritems() -%}
- {{ key.ljust(min_width) }} :        {{ value | sanitize }}
{% endfor -%}
'''
ENVIRONMENT = jinja2.Environment()

ENVIRONMENT.globals.update({
    'command_line': " ".join([value if value else "''" for value in sys.argv]),
    'now': datetime.utcnow,
})
ENVIRONMENT.filters.update({
    'sanitize': sanitize,
    'test_identifier': to_test_identifier,
    'empty': empty,
})

HUMAN_READABLE_TEMPLATE = ENVIRONMENT.from_string(HUMAN_READABLE_TEMPLATE_STR)


def stream_human_readable(test_identifier, configuration, collection, default_config, layers,
                          override_config):
    """
    Stream the configuration into an iterable human readable string.

    :param dict() test_identifier: The project, variant, task, test and thread_level that
    identifies this test.
    :param list(dict) configuration: The configuration data.
    :param pymongo.collection collection: The collection instance.
    :param dict default_config: The default configuration.
    :param list(dict) layers: The list of configuration layers.
    :param OutlierConfiguration override_config: The configuration supplied from the CLI params.
    :return: The human readable outliers.
    """
    # pylint: disable=too-many-arguments
    width = max(len(key) for key in configuration._asdict().keys())
    return HUMAN_READABLE_TEMPLATE.stream(
        _id=test_identifier,
        configuration=configuration._asdict(),
        collection=collection,
        test_identifier=test_identifier,
        default_config=default_config._asdict(),
        layers=layers,
        override_config=override_config._asdict(),
        min_width=width)


def view_configuration(test_identifier, command_config):
    """ View the configuration. """
    model = ConfigurationModel(command_config.mongo_uri)
    layers = list(model.get_configuration(test_identifier))
    override_config = OutlierConfiguration()
    configuration = combine_outlier_configs(test_identifier, layers, override_config)

    for line in stream_human_readable(test_identifier, configuration, model.collection,
                                      DEFAULT_CONFIG, layers, override_config):
        print(line, end='')


def set_configuration(test_identifier, configuration, command_config):
    """ Set the configuration. """
    model = ConfigurationModel(command_config.mongo_uri)
    model.set_configuration(test_identifier, configuration)


def unset_configuration(test_identifier, configuration, command_config):
    """ unset the configuration. """
    model = ConfigurationModel(command_config.mongo_uri)
    model.unset_configuration(test_identifier, configuration)


def delete_configuration(test_identifier, command_config):
    """ Set the configuration. """
    model = ConfigurationModel(command_config.mongo_uri)
    model.delete_configuration(test_identifier)
