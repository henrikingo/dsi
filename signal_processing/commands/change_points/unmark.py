"""
Functionality to unmark change points.
"""
import click

from signal_processing.change_points import unmark
from signal_processing.commands import helpers


@click.command(name='unmark')
@click.pass_obj
@click.option(
    '--exclude',
    'exclude_patterns',
    multiple=True,
    help='Exclude all points matching this pattern. This parameter can be provided ' +
    'multiple times.')
@click.option(
    '--processed-type',
    'processed_type',
    type=click.Choice(['any'] + helpers.PROCESSED_TYPES),
    default='any',
    required=True,
    help='The value to set processed_type.')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
@click.argument('thread_level', required=False)
def unmark_command(command_config, exclude_patterns, processed_type, revision, project, variant,
                   task, test, thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Unmark (Delete) an existing processed change point(s).
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
    # dry run on all sys-perf points
    $> change-points unmark $revision sys-perf -n
\b
    # unmark all *existing* sys-perf change points for a specific sys perf revision
    $> change-points unmark $revision sys-perf
\b
    # unmark some existing acknowledged processed change points
    $> change-points unmark $revision sys-perf linux-1-node-replSet --processed-type acknowledged
    $> change-points unmark $revision sys-perf '/linux-.-node-replSet/' \\
    --processed-type acknowledged
    $> change-points unmark $revision sys-perf revision linux-1-node-replSet \\
    change_streams_latency --exclude '/^(fio_|canary_)/' --processed-type acknowledged
    $> change-points unmark $revision sys-perf linux-1-node-replSet change_streams_latency \\
       '/^(fio_|canary_)/' --processed-type acknowledged
\b
    # unmark all hidden points matching revision sys-perf find_limit-useAgg 8 thread level
    $> change-points unmark  $revision sys-perf '' '' find_limit-useAgg 8 --processed-type hidden
    #  unmark all points matching revision sys-perf find_limit-useAgg 8 thread level
    $> change-points unmark  $revision sys-perf '' '' find_limit-useAgg 8
\b
    # unmark all acknowledged points matching revision sys-perf find_limit-useAgg 8 thread level as
    # acknowledged
    $> change-points update  $revision sys-perf '' '' find_limit-useAgg 8 \\
    --processed-type acknowledged
\b
    # unmark all hidden points matching revision sys-perf find_limit-useAgg all thread level
    $> change-points update $revision sys-perf '' '' find_limit-useAgg --processed-type hidden
    #  unmark all points matching revision sys-perf find_limit-useAgg all thread level
    $> change-points update $revision sys-perf '' '' find_limit-useAgg
\b
    # unmark all acknowledged revision sys-perf find_limit-useAgg all thread level as acknowledged
    $> change-points update $revision sys-perf '' '' find_limit-useAgg '' \\
    --processed-type acknowledged
"""
    query = helpers.process_params(
        project, variant, task, test, revision=revision, thread_level=thread_level)
    unmark.unmark_change_points(None if processed_type == 'any' else processed_type, query,
                                helpers.process_excludes(exclude_patterns), command_config)
