"""
Command to list build failures and their linked change points.
"""
import click
import structlog

from signal_processing.change_points import list_build_failures
from signal_processing.commands import helpers

LOG = structlog.getLogger(__name__)


@click.command(name='list-build-failures')
@click.pass_obj
@click.option(
    '--human-readable',
    'human_readable',
    is_flag=True,
    help='Print output in a more human-friendly output.')
@click.argument('revision', required=True)
@click.argument('project', required=True)
@click.argument('variant', required=False)
@click.argument('task', required=False)
@click.argument('test', required=False)
def list_build_failures_command(command_config, human_readable, revision, project, variant, task,
                                test):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Print list of build failures and their linked change points.

Arguments can be string or patterns, A pattern starts with /.

\b
REVISION, the revision of the change point.
PROJECT, the project name or a regex (like /^sys-perf-3.*/ or /^(sys-perf|performance)$/).
VARIANT, the build variant or a regex.
TASK, the task name or a regex.
TEST, the test name or a regex.
\b
You can use '' in place of VARIANT, TASK, TEST, if you want to match all. See the examples.
\b
Examples:
    $> revision=a1b225bcf0e9791b14649df385b3f3f9710a98ab
\b
    # List all build failures
    $> change-points list-build-failures
\b
    # List all build failures for a revision
    $> change-points list-build-failures $revision
\b
    # List sys-perf build failures for a revision
    $> change-points list-build-failures $revision sys-perf
\b
    # List sys-perf build failures (any revision)
    $> change-points list-build-failures '' sys-perf
\b
    # List build failures matching criteria
    $> change-points list-build-failures $revision sys-perf linux-1-node-replSet
    $> change-points list-build-failures $revision sys-perf '/linux-.-node-replSet/'
\b
    # List all build failures with sys-perf find_limit-useAgg (any revision)
    $> change-points list-build-failures '' sys-perf '' '' find_limit-useAgg
\b
    # List build failures in a more human-friendly format
    $> change-points list-build-failures --human-readable
    $> change-points list-build-failures $revision sys-perf linux-1-node-replSet --human-readable
"""
    query = helpers.process_params(project, variant, task, test, revision=revision)
    list_build_failures.list_build_failures(query, human_readable, command_config)
