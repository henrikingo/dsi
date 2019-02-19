"""
Command to mark change points.
"""
import click

from signal_processing.outliers import unmark_outliers
from signal_processing.commands import helpers


@click.command(name='unmark')
@click.pass_obj
@click.argument('revision', required=True, callback=helpers.validate_outlier_param)
@click.argument('project', required=True, callback=helpers.validate_outlier_param)
@click.argument('variant', required=True, callback=helpers.validate_outlier_param)
@click.argument('task', required=True, callback=helpers.validate_outlier_param)
@click.argument('test', required=True, callback=helpers.validate_outlier_param)
@click.argument('thread_level', required=True, callback=helpers.validate_outlier_param)
def unmark_outliers_command(command_config, revision, project, variant, task, test, thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Unmark a single outlier.This process removes the matching outlier from the
marked_outliers collection.

Arguments can be strings or patterns, A pattern starts with /.

\b
REVISION, the revision of the outlier. This parameter is mandatory.
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
    # mark non canary change_streams_latency linux-1-node-replSet sys-perf points for a given
    # revision
    $> outliers mark $revision sys-perf linux-1-node-replSet bestbuy_query \
       canary_client-cpuloop-10x 1
"""
    query = helpers.process_params_for_points(
        project, variant, task, test, revision=revision, thread_level=thread_level)
    unmark_outliers.unmark_outlier(query, command_config)
