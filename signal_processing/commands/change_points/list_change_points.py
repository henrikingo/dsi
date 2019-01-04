# -*- coding: utf-8 -*-
"""
Functionality to list change points.
"""
import click
import structlog

from signal_processing.change_points import list_change_points
from signal_processing.commands import helpers

LOG = structlog.getLogger(__name__)


@click.command(name='list')
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
    multiple=True,
    help='tests are excluded if this matches. It can be provided multiple times. ' +
    'A regex starts with a "/" char')
@click.option(
    '--point-type',
    type=click.Choice(list_change_points.VALID_CHANGE_POINT_TYPES),
    default=list_change_points.CHANGE_POINT_TYPE_UNPROCESSED,
    help='The type of point to list.')
@click.option(
    '--limit',
    callback=helpers.validate_int_none_options,
    default='10',
    help='''The maximum number of change points to display.
    The default is 10. Use \'None\' for no limit.''')
@click.option(
    '--no-older-than',
    callback=helpers.validate_int_none_options,
    default='14',
    help='''Don't consider points older than this number of days.
A perf BB rotation is 2 weeks, so 14 days seems appropriate''')
@click.option(
    '--human-readable/--no-human-readable',
    'human_readable',
    is_flag=True,
    default=True,
    help='Print output in a more human-friendly output.')
@click.option(
    '--show-canaries/--hide-canaries',
    'show_canaries',
    is_flag=True,
    default=False,
    help='Should canaries be shown (defaults to hidden). The filtering happens in the database.')
@click.option(
    '--processed-type',
    'processed_types',
    type=click.Choice(helpers.PROCESSED_TYPES),
    default=[helpers.PROCESSED_TYPE_ACKNOWLEDGED],
    required=False,
    multiple=True,
    help='When displaying the processed list, the processed_type must be one of the supplied types.'
)
@click.option(
    '--show-wtdevelop/--hide-wtdevelop',
    'show_wtdevelop',
    is_flag=True,
    default=False,
    help='Should wtdevelop be shown (defaults to hidden). The filtering happens in the database.')
@click.option('--revision', 'revision', default=None, help='Specify a revision, defaults to None.')
@click.argument('project', required=False)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def list_command(command_config, exclude_patterns, point_type, limit, no_older_than, human_readable,
                 show_canaries, show_wtdevelop, processed_types, revision, project, variant, task,
                 test, thread_level):
    # pylint: disable=too-many-arguments, too-many-locals, too-many-function-args
    """
    List unprocessed / processed or raw change points (defaults to unprocessed).
The points are grouped by revision and project to reduce clutter. The default is to only show groups
with a change point in the last 14 days. (use --no-older-than=None for all or --no-older-than=30 to
view older change points). The points are sorted by the min magnitude (ascending) of change. By
default, the backing aggregation removes canary test or wtdevelop tasks. These can be viewed with
the --show-canaries or --show-wtdevelop options. The output defaults to human readable format (which
is also valid markdown).

Arguments can be string or patterns, A pattern starts with /.

\b
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
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
    # list unprocessed change points
    $> change-points list                           # list 10
    $> change-points list --point-type unprocessed  # list 10
    $> change-points list --limit None              # list all
\b
    # list processed change points
    $> change-points list --point-type processed
\b
    # list change points
    $> change-points list --point-type raw
\b
    # list unprocessed change points for a revision
    $> change-points list --revision $revision
\b
    # list sys perf unprocessed change points for a revision
    $> change-points list sys-perf --revision $revision # list all sys-perf points for revision
\b
    # list sys perf unprocessed change points (any revision)
    $> change-points list sys-perf
\b
    # list unprocessed change points matching criteria
    $> change-points list revision sys-perf linux-1-node-replSet --revision $revision
    $> change-points list sys-perf '/linux-.-node-replSet/' --revision $revision
\b
    # list non canary unprocessed change points for sys-perf linux-1-node-replSet
    # change_streams_latency and revision
    $> change-points list sys-perf linux-1-node-replSet change_streams_latency \\
    '/^(fio_|canary_|Network)/' --revision $revision
\b
    # list all non canary unprocessed change points for sys-perf linux-1-node-replSet
    # change_streams_latency and revision
    $> change-points list sys-perf linux-1-node-replSet change_streams_latency \\
    --exclude '/^(fio_|canary_|Network)/' --revision $revision
\b
    # list all the unprocessed sys-perf find_limit-useAgg (any revision)
    $> change-points list sys-perf '' '' find_limit-useAgg
\b
    # list all the acknowledged processed sys-perf change points
    $> change-points list sys-perf  --point-type processed --processed-type acknowledged
    $> change-points list sys-perf  --point-type processed
\b
    # list all the hidden processed sys-perf change points
    $> change-points list sys-perf  --point-type processed --processed-type hidden
\b
    # list all the processed sys-perf change points
    $> change-points list sys-perf  --point-type processed --processed-type acknowledged\
    --processed-type hidden
"""
    query = helpers.process_params(
        project, variant, task, test, revision=revision, thread_level=thread_level)
    list_change_points.list_change_points(
        change_point_type=point_type,
        query=query,
        limit=limit,
        no_older_than=no_older_than,
        human_readable=human_readable,
        hide_canaries=not show_canaries,
        hide_wtdevelop=not show_wtdevelop,
        exclude_patterns=helpers.process_excludes(exclude_patterns),
        processed_types=processed_types,
        command_config=command_config)
