"""
Command to mark outliers.
"""
import click
import structlog

from signal_processing.outliers import whitelist_task
from signal_processing.commands import helpers

LOG = structlog.getLogger(__name__)


@click.group(name='whitelist')
@click.version_option()
def whitelist_task_group():
    """
    Whitelist commands such as list, add and remove.

Arguments can be strings or patterns, A pattern starts with /.

\b
REVISION, the revision of the outlier. This parameter is mandatory for add and remove sub-commands.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This
parameter is mandatory for all sub-commands.
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, THREADS if you want to match all. See the examples.
\b
List Examples: (See 'outliers whitelist list --help ' for full details)
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
    # list all whitelists for sys-perf project
    $> outliers whitelist list sys-perf
\b
    # list all whitelists for sys-perf project, linux-1-node-replSet variant
    $> outliers whitelist list sys-perf linux-1-node-replSet
\b
    # list all whitelists for sys-perf project, any variant on the bestbuy_query task
    $> outliers whitelist list sys-perf '' bestbuy_query
\b
    # list all whitelists for sys-perf project, standalone and 1 node variants variant on
    # any bestbuy task
    $> outliers whitelist list sys-perf '/^linux-(standalone|1-node)/' '/^bestbuy/

\b
Add Examples: (See 'outliers whitelist add --help ' for full details)
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
    # Add whitelists for all sys-perf project tasks for the given revision
    $> outliers whitelist add $revision sys-perf
    $> outliers --dry-run whitelist add $revision sys-perf # dry run of command
    $> outliers -n whitelist add $revision sys-perf        # dry run of command
\b
    # Add whitelists for all sys-perf project, linux-1-node-replSet variant tasks for the given
    # revision
    $> outliers whitelist add $revision sys-perf linux-1-node-replSet
\b
    # Add whitelists for all sys-perf project, any variant on the bestbuy_query task for the given
    # revision
    $> outliers whitelist add $revision sys-perf '' bestbuy_query
\b
    # Add whitelists for all sys-perf project, standalone and 1 node variants and any bestbuy
    # tasks for the given revision
    $> outliers whitelist list sys-perf '/^linux-(standalone|1-node)/' '/^bestbuy/

\b
Remove Examples: (See 'outliers whitelist remove --help ' for full details)
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
    # Remove whitelists for all sys-perf project tasks for the given revision
    $> outliers whitelist add $revision sys-perf
    $> outliers --dry-run whitelist add $revision sys-perf # dry run of the command.
\b
    # Remove whitelists for all sys-perf project, linux-1-node-replSet variant tasks for the given
    # revision
    $> outliers whitelist add $revision sys-perf linux-1-node-replSet
\b
    # Remove whitelists for all sys-perf project, any variant on the bestbuy_query task for the
    # given revision
    $> outliers whitelist add $revision sys-perf '' bestbuy_query
\b
    # Remove whitelists for all sys-perf project, standalone and 1 node variants and any bestbuy
    # tasks for the given revision
    $> outliers whitelist list sys-perf '/^linux-(standalone|1-node)/' '/^bestbuy/
"""
    pass


@whitelist_task_group.command(name='list')
@click.pass_context
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.option('--revision', 'revision', default=None, help='Specify a revision, defaults to None.')
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
    '--show-wtdevelop/--hide-wtdevelop',
    'show_wtdevelop',
    is_flag=True,
    default=False,
    help='Should wtdevelop be shown (defaults to hidden). The filtering happens in the database.')
def list_command(context, project, variant, task, revision, limit, no_older_than, human_readable,
                 show_wtdevelop):
    """
    List Whitelists.
The default is to only show whitelists in the last 14 days. (use --no-older-than=None for all or
--no-older-than=30 to view older whitelists, age is based on the timestamp in the objectid). The
whitelists are sorted by the order. By default, the backing aggregation removes
wtdevelop tasks. These can be viewed with the --show-wtdevelop options. The output defaults to
human readable format (which is also valid markdown).

Arguments can be string or patterns, A pattern starts with /.

\b
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
\b
You can use '' in place of VARIANT, TASK if you want to match all. See the examples.
\b
Examples:
\b
    # list whitelists
    $> outliers whitelist list sys-perf                # list 10
    $> outliers whitelist list sys-perf --limit None   # list all
\b
    # list whitelists for a revision
    $> outliers whitelist list sys-perf --revision $revision
\b
    # list whitelists matching criteria
    $> outliers whitelist list sys-perf linux-1-node-replSet --revision $revision
    $> outliers whitelist list sys-perf '/linux-.-node-replSet/' --revision $revision
\b
    # list whitelists matching for sys-perf linux-1-node-replSet and revision
    $> outliers whitelist list sys-perf linux-1-node-replSet change_streams_latency \\
    --revision $revision
\b
    # list all the unprocessed sys-perf find_limit-useAgg (any revision)
    $> outliers whitelist list sys-perf '' bestbuy_agg
"""
    # pylint: disable=too-many-arguments
    LOG.debug('List Outlier Task Whitelists', project=project, variant=variant, task=task)

    command_config = context.obj

    task_identifier = helpers.process_params_for_whitelist(revision, project, variant, task)
    whitelist_task.list_whitelist(task_identifier, limit, no_older_than, human_readable,
                                  show_wtdevelop, command_config)


@whitelist_task_group.command(name='add')
@click.pass_context
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
def add_command(context, revision, project, variant, task):
    """
    Add Whitelists.

Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the task. This parameter is mandatory.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This
parameter is mandatory.
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
\b
You can use '' in place of VARIANT, TASK if you want to match all. See the examples.
\b
Examples:
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
    # Add whitelists for all sys-perf project tasks for the given revision
    $> outliers whitelist add $revision sys-perf
    $> outliers --dry-run whitelist add $revision sys-perf  # do a dry run of the command
\b
    # Add whitelists for all sys-perf project, linux-1-node-replSet variant tasks for the given
    # revision
    $> outliers whitelist add $revision sys-perf linux-1-node-replSet
\b
    # Add whitelists for all sys-perf project, any variant on the bestbuy_query task for the given
    # revision
    $> outliers whitelist add $revision sys-perf '' bestbuy_query
\b
    # Add whitelists for all sys-perf project, standalone and 1 node variants and any bestbuy
    # tasks for the given revision
    $> outliers whitelist list sys-perf '/^linux-(standalone|1-node)/' '/^bestbuy/
"""
    # pylint: disable=too-many-arguments
    LOG.debug(
        'Add Outlier Task Whitelists',
        revision=revision,
        project=project,
        variant=variant,
        task=task)

    command_config = context.obj

    task_identifier = helpers.process_params_for_whitelist(revision, project, variant, task)
    whitelist_task.add_whitelist(task_identifier, command_config)


@whitelist_task_group.command(name='remove')
@click.pass_context
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=True)
@click.argument('task', required=True)
def remove_command(context, revision, project, variant, task):
    """
    Remove Whitelists.

Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the task. This parameter is mandatory.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/). This
parameter is mandatory.
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
\b
You can use '' in place of VARIANT, TASK if you want to match all. See the examples.
\b
Examples:
    $> revision=bad5afd612e8fc917fb035d8333cffd7d68a37cc
    # Remove whitelists for all sys-perf project tasks for the given revision
    $> outliers whitelist add $revision sys-perf
    $> outliers --dry-run whitelist add $revision sys-perf # do a dry run of the command
    $> outliers -n whitelist add $revision sys-perf        # do a dry run of the command
\b
    # Remove whitelists for all sys-perf project, linux-1-node-replSet variant tasks for the given
    # revision
    $> outliers whitelist add $revision sys-perf linux-1-node-replSet
\b
    # Remove whitelists for all sys-perf project, any variant on the bestbuy_query task for the
    # given # revision
    $> outliers whitelist add $revision sys-perf '' bestbuy_query
\b
    # Remove whitelists for all sys-perf project, standalone and 1 node variants and any bestbuy
    # tasks for the given revision
    $> outliers whitelist list sys-perf '/^linux-(standalone|1-node)/' '/^bestbuy/
"""
    # pylint: disable=too-many-arguments
    LOG.debug(
        'Remove Outlier Task Whitelists',
        revision=revision,
        project=project,
        variant=variant,
        task=task)

    command_config = context.obj

    task_identifier = helpers.process_params_for_whitelist(revision, project, variant, task)
    whitelist_task.remove_whitelist(task_identifier, command_config)
