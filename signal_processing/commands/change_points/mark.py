"""
Functionality to mark change points.
"""
import click
import structlog

from signal_processing.commands import helpers as helpers

from signal_processing.commands.helpers import stringify_json, filter_excludes

LOG = structlog.getLogger(__name__)

KEYS = ('suspect_revision', 'project', 'variant', 'task', 'test', 'thread_level')
"""
A tuple containing the keys for a unique identifier for a point.
"""


def get_identifier(point):
    """
    Get the identifier for a point.

    :param dict point: The full data for the point.
    :return: TYhe unique identifier for a point.
    :rtype: dict.
    """
    return {key: point[key] for key in KEYS}


def mark_change_points(processed_type, query, exclude_patterns, command_config):
    """
    Mark a point as hidden or real.

    :param str processed_type: Set the type.
    :see signal_processing.helpers.PROCESSED_TYPES.
    :param dict query: Find change points matching this query.
    :param list(re) exclude_patterns: Filter any points matching this list of excludes.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug('mark points', processed_type=processed_type)
    collection = command_config.change_points

    for point in filter_excludes(collection.find(query), query.keys(), exclude_patterns):
        point['processed_type'] = processed_type
        del point['_id']
        LOG.info("matched %s\n", stringify_json(point, compact=command_config.compact))
        if not command_config.dry_run:
            result = command_config.processed_change_points.update(
                get_identifier(point), {"$set": point}, upsert=True)
            LOG.debug('mark points', result=result)


@click.command(name='mark')
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
    multiple=True,
    help='Exclude all points matching this pattern. This parameter can be provided ' +
    'multiple times.')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def mark_command(command_config, exclude_patterns, revision, project, variant, task, test,
                 thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Mark change point(s) as acknowledged.This process creates a copy of a change_points (ephemeral
output of the signal processing algorithm) in the (persistent) processed_change_point collection.

Arguments can be strings or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point. This parameter is mandatory.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This
parameter is mandatory.
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
THREADS, the thread level or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, THREADS if you want to match all. See the examples.
\b
Examples:
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
\b
    # dry run mark all sys-perf points for a given revision
    $> change-points mark $revision sys-perf -n
\b
    # mark all sys-perf points for a given revision
    $> change-points mark $revision sys-perf
\b
    # mark all linux-1-node-replSet sys-perf points for a given revision
    $> change-points mark $revision sys-perf linux-1-node-replSet
\b
    # mark all replSet sys-perf points for a given revision
    $> change-points mark $revision sys-perf '/linux-.-node-replSet/'
\b
    # mark all non canary change_streams_latency linux-1-node-replSet sys-perf points for a given
    # revision
    $> change-points mark $revision sys-perf revision linux-1-node-replSet change_streams_latency
    --exclude '/^(fio_|canary_)/'
\b
    # mark all canary change_streams_latency linux-1-node-replSet sys-perf points for a given
    # revision
    $> change-points mark $revision sys-perf linux-1-node-replSet change_streams_latency \
       '/^(fio_|canary_)/'
\b
    #  mark all the revision sys-perf find_limit-useAgg 8 thread level
    $> change-points mark $revision sys-perf '' '' find_limit-useAgg 8
\b
    #  mark all the revision sys-perf find_limit-useAgg all thread level
    $> change-points mark $revision sys-perf '' '' find_limit-useAgg
    $> change-points mark $revision sys-perf '' '' find_limit-useAgg ''
"""
    query = helpers.process_params(
        project, variant, task, test, revision=revision, thread_level=thread_level)
    mark_change_points(helpers.PROCESSED_TYPE_ACKNOWLEDGED, query,
                       helpers.process_excludes(exclude_patterns), command_config)


@click.command(name='hide')
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
    multiple=True,
    help='tests are excluded if this matches. It can be provided multiple times. ' +
    'A regex starts with a "/" char')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def hide_command(command_config, exclude_patterns, revision, project, variant, task, test,
                 thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Hide a change point(s). This process creates a copy of a change_points (ephemeral output of
the signal processing algorithm) in the (persistent) processed_change_point collection.

Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point. This parameter is mandatory.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This
parameter is mandatory.
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
THREADS, the thread level or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, THREADS if you want to match all. See the
examples.
\b
Examples:
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
\b
    # dry run on all sys-perf points for a given revision
    $> change-points hide $revision sys-perf -n
\b
    # hide sys-perf change points
    $> change-points hide $revision sys-perf
    $> change-points hide $revision sys-perf linux-1-node-replSet
    $> change-points hide $revision sys-perf '/linux-.-node-replSet/'
    $> change-points hide $revision sys-perf revision linux-1-node-replSet \\
       change_streams_latency  --exclude '/^(fio_|canary_)/'
    $> change-points hide $revision sys-perf linux-1-node-replSet change_streams_latency \\
    '/^(fio_|canary_)/'
\b
    #  hide all the revision sys-perf find_limit-useAgg 8 thread level
    $> change-points hide $revision sys-perf '' '' find_limit-useAgg 8
\b
    #  hide all the revision sys-perf find_limit-useAgg all thread level
    $> change-points hide  $revision sys-perf '' '' find_limit-useAgg
    $> change-points hide $revision sys-perf '' '' find_limit-useAgg ''
"""

    query = helpers.process_params(
        project, variant, task, test, revision=revision, thread_level=thread_level)
    mark_change_points(helpers.PROCESSED_TYPE_HIDDEN, query,
                       helpers.process_excludes(exclude_patterns), command_config)
