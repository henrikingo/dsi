#!/usr/bin/env python2.7
"""
Cli wrapper for various change point operations

To get access to the help try the following command:

    $> change-points help
"""
# TODO: remove the following line on completion of PERF-1608.
# pylint: disable=too-many-lines

from __future__ import print_function

import os

import click
import structlog

import signal_processing.commands.helpers as helpers
import signal_processing.commands.change_points.attach as attach
import signal_processing.commands.change_points.compare as compare
import signal_processing.commands.change_points.compute as compute
import signal_processing.commands.change_points.list_build_failures as list_build_failures
import signal_processing.commands.change_points.list_change_points as list_change_points
import signal_processing.commands.change_points.list_failures as list_failures
import signal_processing.commands.change_points.manage as manage
import signal_processing.commands.change_points.mark as mark
import signal_processing.commands.change_points.unmark as unmark
import signal_processing.commands.change_points.update as update
import signal_processing.commands.change_points.visualize as visualize
from bin.common import log

DB = 'perf'
PROCESSED_CHANGE_POINTS = 'processed_change_points'
CHANGE_POINTS = 'change_points'
POINTS = 'points'
BUILD_FAILURES = 'build_failures'

LOG = structlog.getLogger(__name__)

APP_NAME = os.environ.get('DSI_APP_NAME', 'change-points')
"""
The name to use to look for the application configuration. Don't change
from the default 'change-points' unless you have a compelling reason or
you want to test.
"""

APP_CONF_LOCATION = os.environ.get('DSI_APP_CONF_LOCATION', None)
"""
The config files are looked up in the following locations (in the following order):
  1. The current directory.
  1. The DSI_APP_CONF_LOCATION env var.
  1. The directory returned from click.get_app_dir with force_posix set to True.
See `click.get_app_dir<http://click.pocoo.org/5/api/#click.get_app_dir>'.
"""

CONTEXT_SETTINGS = dict(
    default_map=helpers.read_default_config(APP_NAME, APP_CONF_LOCATION),
    help_option_names=['-h', '--help'],
    max_content_width=120)


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option(
    '-d', '--debug', count=True, help='Enable debug output, you can pass multiple -ddddd etc.')
@click.option('-l', '--logfile', default=None, help='The log file to write to, defaults to None.')
@click.option('-o', '--out', default='/tmp', help='The location to save any files in.')
@click.option(
    '-f', '--format', 'file_format', default='png', help='The format to save any files in.')
@click.option(
    '-u',
    '--mongo-uri',
    default='mongodb://localhost:27017/' + DB,
    help='MongoDB connection string. The database name comes from here too.',
    envvar="DSI_MONGO_URI")
@click.option('-q', '--queryable', default=False, help='Print ids as queries')
@click.option('-n', '--dry-run', is_flag=True, default=False, help='Do not actually run anything.')
@click.option(
    '-c', '--compact/--expanded', 'compact', default=True, help='Display objects one / line.')
@click.option(
    '--style', default=['bmh'], multiple=True, help='The default matplot lib style to use.')
@click.option('--token-file', default=None, envvar='DSI_TOKEN_FILE')
@click.option('--mongo-repo', 'mongo_repo', default='~/src', envvar='DSI_MONGO_REPO')
@click.pass_context
def cli(context, debug, logfile, out, file_format, mongo_uri, queryable, dry_run, compact, style,
        token_file, mongo_repo):
    """
For a list of styles see 'style sheets<https://matplotlib.org/users/style_sheets.html>'.

You can create a config file to hold commonly used config parameters.

The CLI looks for configuration files in the following locations (int his order):

\b
1. ./.change-points
2. ${DSI_APP_CONF_LOCATION}/.change-points.
3. ~/.change-points or whatever is returned by
[click_get_app_dir](http://click.pocoo.org/5/api/#click.get_app_dir) for your OS.

The file is assumed to be yaml. A sample config file looks like:

\b
# -*-yaml-*-
# Enable debug if debug > 0, you can set higher levels.
debug: 0
# The log file to write to, defaults to None.
logfile: /tmp/change-points.log
# MongoDB connection string. The database name comes from here too.
mongo_uri: mongodb://localhost/perf
# Possible styles are list at https://matplotlib.org/users/style_sheets.html
# 'style' is an array and you can provide multiple values.
style:
  - bmh
token_file: ./config.yml
mongo_repo: ~/git/mongo-for-hashes
# The following sections are for the sub commands.
# These are over laid on the cli params (above).
compare:
  progressbar: false
  no_older_than: 14
  show: true
compute:
  # Note: Don't add help to a command as it would be confusing. It will
  # always just print help and exit.
  progressbar: true
list:
  limit: 20
  no_older_than: 20
list-build-failures:
  human_readable: true
mark:
  exclude_patterns:
    - this
    - that
update:
  exclude:
    - this
    - that
visualize:
  sigma: 2.0

__Note:__ dashes on the command names (e.g. 'list-build-failures') and underscores on the
field names ('human_readable').

The configuration values are applied in the following order:

\b
   1. Defaults as defined in the help.
   2. Values specified in the configuration file.
   3. Values in an env var (if applicable).
   4. Command line parameter values.


"""
    # pylint: disable=missing-docstring, too-many-arguments, too-many-locals
    config = helpers.CommandConfiguration(
        debug=debug,
        out=out,
        log_file=logfile,
        file_format=file_format,
        mongo_uri=mongo_uri,
        queryable=queryable,
        dry_run=dry_run,
        compact=compact,
        style=style,
        token_file=token_file,
        mongo_repo=mongo_repo)
    context.obj = config
    if context.invoked_subcommand is None:
        print(context.get_help())
    log.setup_logging(config.debug > 0, filename=config.log_file)


@cli.command(name='help')
@click.pass_context
def help_command(context):
    """
    Show the help message and exit.
    """
    print(context.parent.get_help())


cli.add_command(mark.mark_command)
cli.add_command(mark.hide_command)
cli.add_command(unmark.unmark_command)
cli.add_command(update.update_command)
cli.add_command(list_change_points.list_command)
cli.add_command(compare.compare_command)
cli.add_command(compute.compute_command)
cli.add_command(manage.manage_command)
cli.add_command(visualize.visualize_command)
cli.add_command(list_build_failures.list_build_failures_command)
cli.add_command(list_failures.list_failures_command)
cli.add_command(attach.attach_command)
cli.add_command(attach.detach_command)
