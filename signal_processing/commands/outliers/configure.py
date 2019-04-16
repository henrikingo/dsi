"""
CLI for outlier detection configuration.
"""
from __future__ import print_function

from StringIO import StringIO

import yaml

import click
import structlog
from signal_processing.commands import helpers
from signal_processing.commands.helpers import extract_pattern
from signal_processing.model.configuration import validate_configuration
from signal_processing.outliers import configure

LOG = structlog.getLogger(__name__)


def fixup_config(config):
    """
    Convert any config patterns to regexes.
    :param dict config: The configuration
    :return: A dict().
    """
    return {
        key: extract_pattern(value) if key.endswith('_pattern') else value
        for key, value in config.iteritems()
    }


def validate_json_exclusive(context, param, value):
    """
    Validate that only one of json and json_file are set.

    :param object context: The click context object.
    :param object param: The click parameter definition.
    :param str value: The value for the --limit option.
    :return: value.
    :raises: click.BadParameter if both parameters are supplied.
    """
    #pylint: disable=unused-argument
    if context.params.get('json', None) and context.params.get('json_file', None):
        raise click.BadParameter('json and json-file are mutually exclusive.')
    return value


@click.group(name='configure')
@click.version_option()
def configure_group():
    """
Command line for the outlier detection configuration.

\b
The configuration is generated from:
  - The default configuration, as defined in signal_processing.model.configuration.DEFAULT_CONFIG.
  - The configuration layers from the identifier. The layers are generated from the permutations
of the project, variant, task, test and thread_level. If values are supplied for all the parts then
the layers are:
       - project
       - project, variant
       - project, variant, task
       - project, variant, task, test (only applicable to outlier detection)
       - project, variant, task, test, thread_level  (only applicable to outlier detection)

The final configuration is generated by merging the default and the applicable layers
(with all null value removed).

\b
The GESD configurable options are:
  - max_outliers: A float value between 0 and 1.0 which is used to determine the value of the
maximum number of outliers. A 0.1 implies check 10% of results, 0.5 implies 50% and so on. The
default value is 0.15 (see signal_processing.model.configuration.DEFAULT_MAX_OUTLIERS_PERCENTAGE).
   - mad: A flag controlling the use of Median Absolute Deviation as part of the outlier
calculation.
When set to True MAD is used, otherwise a z score (the number of standard deviations from the
mean) is used. The default value is False (see
signal_processing.model.configuration.DEFAULT_USE_MAD).
   - significance_level: The value to use for the significance test. The default value is 0.05
   (see signal_processing.model.configuration.DEFAULT_SIGNIFICANCE_LEVEL).

\b
So for example, for max_outliers, given a test_identifier of {project:'performance',
variant:'linux-wt-repl', task:'misc', test:'Commands.FindAndModifyInserts', thread_level: '1'}:
   - default is 0.15
   - ('performance', ) is 0.10
   - ('performance', 'linux-wt-repl') is not set (null)
   - ('performance', 'linux-wt-repl', 'misc') is not set (null)
   - ('performance', 'linux-wt-repl', 'misc', 'Commands.FindAndModifyInserts') is not set (null)
   - ('performance', 'linux-wt-repl', 'misc', 'Commands.FindAndModifyInserts', '1') is 0.5.
The resultant max_outliers would be the most specific available, 0.5 in this case.

\b
Another example , for mad, given a test_identifier of {project:'performance',
variant:'linux-wt-repl', task:'misc', test:'Commands.FindAndModifyInserts', thread_level: 'max'}::
   - default is False
   - ('performance', ) is 0.10
   - ('performance', 'linux-wt-repl') is not set (null)
   - ('performance', 'linux-wt-repl', 'misc') is not set (null)
   - ('performance', 'linux-wt-repl', 'misc', 'Commands.FindAndModifyInserts') is not set (null).
   - ('performance', 'linux-wt-repl', 'misc', 'Commands.FindAndModifyInserts', 'max') is not set
(null).
The resultant max_outliers would be the most specific available, False in this case.

\b
The configurable options related to automatic outlier reject are:
   - max_consecutive_rejections: Rejection is muted (disabled) once this many consecutive rejections
occur. The default is 3 (see
signal_processing.model.configuration.DEFAULT_MAX_CONSECUTIVE_REJECTIONS).
   - minimum_points: The minimum number of points that must be available before a result can be
automatically rejected. The default is 15 (see
signal_processing.model.configuration.DEFAULT_MINIMUM_POINTS).

Automatic rejection options are only used to the task layer.

\b
So for example, for max_consecutive_rejections, given a task identifier of {project:'sys-perf',
variant:'linux-standalone', task:'bestbuy_agg'}:
   - default is 3
   - ('sys-perf', ) is null
   - ('sys-perf', 'linux-standalone') is 4
   - ('sys-perf', 'linux-standalone', 'bestbuy_agg') is 2
The resultant max_consecutive_rejections would be the most specific available, 2 in this case.

Any values set in the test and thread layers would be ignored.

\b
Another example , for mad, given a test_identifier of {project:'performance',
variant:'linux-wt-repl', task:'misc', test:'Commands.FindAndModifyInserts', thread_level: 'max'}::
   - default is False
   - ('performance', ) is 0.10
   - ('performance', 'linux-wt-repl') is not set (null)
   - ('performance', 'linux-wt-repl', 'misc') is not set (null)
   - ('performance', 'linux-wt-repl', 'misc', 'Commands.FindAndModifyInserts') is not set (null).
   - ('performance', 'linux-wt-repl', 'misc', 'Commands.FindAndModifyInserts', 'max') is not set
(null).
The resultant max_outliers would be the most specific available, False in this case.
\b
The configurable options related to canary and correctness tests are:
   - canary_pattern: The pattern to use to determine if a test name is a canary. The default value
is /^(canary_.*|fio_.*|iperf.*|NetworkBandwidth)$/ (see
signal_processing.model.configuration.DEFAULT_CANARY_PATTERN).
   - correctness_pattern: The pattern to use to determine if a test name is a correctness test.
The default value is /^(db-hash-check|validate-indexes-and-collections|core\\.).*$/ (see
signal_processing.model.configuration.DEFAULT_CORRECTNESS_PATTERN).

Canary and correctness configuration are only used to the task layer.
"""
    pass


@configure_group.command(name='view')
@click.pass_context
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def view_command(context, project, variant, task, test, thread_level):
    """
View the outlier configuration for the identifier.

\b
The configuration is generated by combining the default configuration and the configuration layers.
The layers are generated from the permutations of the project, variant, task, test and thread_level.

\b
See the help output of the configure command for more details, i.e. execute the following command:
   $> outliers configure --help

Examples:

\b
View the configuration generated for a project:
    # default configuration and project layer
    $> outliers configure view sys-perf
\b
View the configuration generated for a project / variant:
    # default configuration and project / variant layers
    $> outliers configure view sys-perf linux-standalone
\b
View the configuration generated for a project / variant  taskl:
    # default configuration and project / variant / task layers.
    # The canary / correctness patterns and max_consecutive_rejections / minimum_points from this
    # combination of layers should be used.
    $> outliers configure view sys-perf linux-standalone bestbuy_agg
\b
View the configuration generated for a project / variant / task / test:
    # default configuration and project / variant / task / test layers.
    # The canary / correctness patterns and max_consecutive_rejections / minimum_points from this
    # combination of layers should not be used.
    $> outliers configure view sys-perf linux-standalone bestbuy_agg 15_5c_update
\b
View the configuration generated for a project / variant / task / test / thread_level:
    # default configuration and project / variant / task / test / thread_level layers.
    # The canary / correctness patterns and max_consecutive_rejections / minimum_points from this
    # combination of layers should not be used.
    $> outliers configure view sys-perf linux-standalone bestbuy_agg 15_5c_update 60

"""
    # pylint: disable=too-many-arguments
    LOG.debug(
        'configure view command starting',
        project=project,
        variant=variant,
        task=task,
        test=test,
        thread_level=thread_level)

    command_config = context.obj
    test_identifier = helpers.process_params(
        project, variant, task, test, thread_level=thread_level)
    configure.view_configuration(test_identifier, command_config)


# pylint: disable=anomalous-backslash-in-string
@configure_group.command(name='set')
@click.pass_context
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
@click.option(
    '--json',
    'config',
    required=False,
    callback=validate_json_exclusive,
    help="A json document containing the configuration fields to set.")
@click.option(
    '--json-file',
    'json_file',
    required=False,
    type=click.File('r'),
    callback=validate_json_exclusive,
    help="A json document containing the configuration fields to set.")
def set_command(context, project, variant, task, test, thread_level, config, json_file):
    """
Set the outlier configuration for a configuration layer.

The set command uses the mongo $set update operator. So only fields that are provided are changed.
Use the unset command to remove a field for a layer or delete command to remove the configuration
for a layer.

See https://docs.mongodb.com/manual/reference/operator/update/set/#behavior
for details about how this works.
\b

The configuration is generated by combining the default configuration and the configuration layers.
The layers are generated from the permutations of the project, variant, task, test and thread_level.

\b
See the help output of the configure command for more details, i.e. execute the following command:
   $> outliers configure --help

Examples:
    Set the configuration generated for a project:

\b
    # default configuration and project layer
    $> cat << END > /tmp/perf.json
{
    "max_outliers": 0.05,
    "mad": true
}
END
    $> outliers configure set sys-perf --json-file /tmp/project.json
    $> cat /tmp/project.json | outliers configure set sys-perf --json-file -
    $> outliers configure set sys-perf --json '{"max_outliers":0.05,"mad":true}'

\b
    # default configuration and project / variant layers
    $> outliers configure set sys-perf linux-standalone --json-file /tmp/project.json

\b
    # default configuration and project / variant / task layers.
    $> outliers configure set sys-perf linux-standalone bestbuy_agg  --json-file /tmp/project.json

\b
    # default configuration and project / variant / task / test layers.
    $> outliers configure set sys-perf linux-standalone bestbuy_agg 15_5c_update \\
    --json-file /tmp/project.json

\b
    # default configuration and project / variant / task / test / thread_level layers.
    $> outliers configure set sys-perf linux-standalone bestbuy_agg 15_5c_update 60 \\
    --json-file /tmp/project.json

The max_consecutive_rejections, minimum_points, canary_pattern and correctness_pattern cannot be
set in test and thread_level layers.

An error will be raised if a configuration with these parameters is attempted on an invalid layer.

\b
For Example:
    $> cat << END > /tmp/invalid.json
{
    "max_consecutive_rejections": 3,
    "minimum_points": 15,
    "canary_pattern": /^(db-hash-check|validate-indexes-and-collections|core\.).*$/,
    "correctness_pattern": /^(canary_.*|fio_.*|iperf.*|NetworkBandwidth)$/
}
END
    $> $ outliers configure set sys-perf linux-standalone bestbuy_agg 15_5c_update 60 \\
    --json-file /tmp/invalid.json
Usage: outliers configure set [OPTIONS] PROJECT [VARIANT] [TASK] [TEST] [THREAD_LEVEL]
\b
Error: Invalid value: max_consecutive_rejections, minimum_points, canary_pattern,
correctness_pattern are not valid for this layer.
\b
    $> $ outliers configure set sys-perf linux-standalone bestbuy_agg 15_5c_update \\
    --json-file /tmp/invalid.json
Usage: outliers configure set [OPTIONS] PROJECT [VARIANT] [TASK] [TEST] [THREAD_LEVEL]
\b
Error: Invalid value: max_consecutive_rejections, minimum_points, canary_pattern,
correctness_pattern are not valid for this layer.
\b
    # The configuration is valid in this case.
    $> outliers configure set sys-perf linux-standalone bestbuy_agg  --json-file /tmp/invalid.json
"""
    # pylint: disable=too-many-arguments
    LOG.debug(
        'configure set command starting',
        project=project,
        variant=variant,
        task=task,
        test=test,
        thread_level=thread_level)

    command_config = context.obj
    test_identifier = helpers.process_params(
        project, variant, task, test, thread_level=thread_level)

    config = yaml.safe_load(StringIO(config) if config else json_file)
    config = fixup_config(config)
    invalid_keys = validate_configuration(test_identifier, config)
    if invalid_keys:
        raise click.BadParameter('{} are not valid for this layer.'.format(', '.join(invalid_keys)))

    configure.set_configuration(test_identifier, config, command_config)


@configure_group.command(name='unset')
@click.pass_context
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
@click.option(
    '--json',
    'config',
    required=False,
    callback=validate_json_exclusive,
    help="A json document containing the configuration fields to set. You can only supply one" +\
         " of --json or --json-file.")
@click.option(
    '--json-file',
    'json_file',
    required=False,
    type=click.File('r'),
    callback=validate_json_exclusive,
    help="A json file containing the configuration fields to set. You can only supply one of" +\
         " --json or --json-file.")
def unset_command(context, project, variant, task, test, thread_level, config, json_file):
    """
Unset the outlier configuration for a configuration layer.

The unset command uses the mongo $unset update operator. So only fields that are provided are
cleared.
Use the unset command to remove a field for a layer or delete command to remove the configuration
for a layer.

Note: the actual values in the unset command are not relevant. So you can use the same file you used
for the set command.

Note: unlike the set command no validation is applied.

See https://docs.mongodb.com/manual/reference/operator/update/unset/#behavior
for details about how this works.
\b

The configuration is generated by combining the default configuration and the configuration layers.
The layers are generated from the permutations of the project, variant, task, test and thread_level.

\b
See the help output of the configure command for more details, i.e. execute the following command:
   $> outliers configure --help

Examples:
    Unset the specified fields for a project:

\b
    # default configuration and project layer
    $> cat << END > /tmp/project.json
{
    "max_outliers": 0.05,
    "mad": true
}
END
    $> outliers configure unset sys-perf --json-file /tmp/project.json
    $> cat /tmp/project.json | outliers configure unset sys-perf --json-file -
    $> outliers configure unset sys-perf --json '{"max_outliers":0.05,"mad":true}'

\b
    # default configuration and project / variant layers
    $> outliers configure unset sys-perf linux-standalone --json-file /tmp/project.json

\b
    # default configuration and project / variant / task layers.
    $> outliers configure unset sys-perf linux-standalone bestbuy_agg  --json-file /tmp/project.json

\b
    # default configuration and project / variant / task / test layers.
    $> outliers configure unset sys-perf linux-standalone bestbuy_agg 15_5c_update \\
    --json-file /tmp/project.json

\b
    # default configuration and project / variant / task / test / thread_level layers.
    $> outliers configure unset sys-perf linux-standalone bestbuy_agg 15_5c_update 60 \\
    --json-file /tmp/project.json

The max_consecutive_rejections, minimum_points, canary_pattern and correctness_pattern cannot be
set in test and thread_level layers but validation is not applied for the unset command.
"""
    # pylint: disable=too-many-arguments
    LOG.debug(
        'configure unset command starting',
        project=project,
        variant=variant,
        task=task,
        test=test,
        thread_level=thread_level)

    command_config = context.obj

    config = yaml.safe_load(StringIO(config) if config else json_file)
    config = fixup_config(config)

    test_identifier = helpers.process_params(
        project, variant, task, test, thread_level=thread_level)
    configure.unset_configuration(test_identifier, config, command_config)


@configure_group.command(name='delete')
@click.pass_context
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def delete_command(context, project, variant, task, test, thread_level):
    """
Delete the outlier configuration for a layer.

The configuration is generated by combining the default configuration and the configuration layers.
The layers are generated from the permutations of the project, variant, task, test and thread_level.

\b
See the help output of the configure command for more details, i.e. execute the following command:
   $> outliers configure --help

Examples:
    Delete the configuration for the specified layer:

\b
    $> outliers configure delete sys-perf
    $> outliers configure delete sys-perf linux-standalone
    $> outliers configure delete sys-perf linux-standalone bestbuy_agg
    $> outliers configure delete sys-perf linux-standalone bestbuy_agg 15_5c_update
    $> outliers configure delete sys-perf linux-standalone bestbuy_agg 15_5c_update 60

"""
    # pylint: disable=too-many-arguments
    LOG.debug(
        'configure command starting',
        project=project,
        variant=variant,
        task=task,
        test=test,
        thread_level=thread_level)

    command_config = context.obj
    test_identifier = helpers.process_params(
        project, variant, task, test, thread_level=thread_level)
    configure.delete_configuration(test_identifier, command_config)
