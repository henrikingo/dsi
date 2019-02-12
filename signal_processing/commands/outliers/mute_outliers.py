"""
Command to mute task.
"""
import click

from signal_processing.outliers import mute
from signal_processing.commands import helpers


@click.command(name='mute')
@click.pass_obj
@click.option(
    '--revision',
    'revision',
    default=None,
    help="""Specify a revision to mute from. if not provided then mute from the latest
revision.""")
@click.argument('project', required=True, callback=helpers.validate_outlier_param)
@click.argument('variant', required=True, callback=helpers.validate_outlier_param)
@click.argument('task', required=True, callback=helpers.validate_outlier_param)
@click.argument('test', required=True, callback=helpers.validate_outlier_param)
@click.argument('thread_level', required=True, callback=helpers.validate_outlier_param)
def mute_outliers_command(command_config, revision, project, variant, task, test, thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Mute outliers for a task.

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
    # mark non canary change_streams_latency linux-1-node-replSet sys-perf points for a given
    # revision
    $> outliers mute sys-perf linux-1-node-replSet bestbuy_query canary_client-cpuloop-10x 1\
       --revision $revision
    # mark non canary change_streams_latency linux-1-node-replSet sys-perf points for a latest
    revision
    $> outliers mute sys-perf linux-1-node-replSet bestbuy_query canary_client-cpuloop-10x 1
"""
    test_identifier = helpers.process_params_for_points(
        project, variant, task, test, revision=revision, thread_level=thread_level)
    mute.mute_outliers(test_identifier, True, command_config)


@click.command(name='unmute')
@click.pass_obj
@click.option(
    '--revision',
    'revision',
    default=None,
    help="""Specify a revision to mute from. if not provided then mute from the latest
revision.""")
@click.argument('project', required=True, callback=helpers.validate_outlier_param)
@click.argument('variant', required=True, callback=helpers.validate_outlier_param)
@click.argument('task', required=True, callback=helpers.validate_outlier_param)
@click.argument('test', required=True, callback=helpers.validate_outlier_param)
@click.argument('thread_level', required=True, callback=helpers.validate_outlier_param)
def unmute_outliers_command(command_config, revision, project, variant, task, test, thread_level):
    # pylint: disable=too-many-arguments, too-many-function-args
    """
    Unmute outliers for a task.

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
    # mark non canary change_streams_latency linux-1-node-replSet sys-perf points for a given
    # revision
    $> outliers unmute sys-perf linux-1-node-replSet bestbuy_query canary_client-cpuloop-10x 1\
       --revision $revision
    # mark non canary change_streams_latency linux-1-node-replSet sys-perf points for a latest
    revision
    $> outliers unmute sys-perf linux-1-node-replSet bestbuy_query canary_client-cpuloop-10x 1
"""
    test_identifier = helpers.process_params_for_points(
        project, variant, task, test, revision=revision, thread_level=thread_level)
    mute.mute_outliers(test_identifier, False, command_config)
