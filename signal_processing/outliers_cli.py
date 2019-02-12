#!/usr/bin/env python2.7
"""
Cli wrapper for various outlier operations

To get access to the help try the following command:

    $> outliers help
"""
from __future__ import print_function

import os

import click
import structlog

from bin.common import log
from signal_processing.commands import helpers
from signal_processing.commands.outliers.config import config_command
from signal_processing.commands.outliers.replay import replay_command
from signal_processing.commands.outliers.manage_outliers import manage_outliers_command
from signal_processing.commands.outliers.mute_outliers import mute_outliers_command,\
    unmute_outliers_command

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


@click.group(name='outliers', context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option(
    '-d', '--debug', count=True, help='Enable debug output, you can pass multiple -ddddd etc.')
@click.option('-l', '--logfile', default=None, help='The log file to write to, defaults to None.')
@click.option('-o', '--out', default='/tmp', help='The location to save any files in.')
@click.option(
    '-f',
    '--format',
    'file_format',
    default='gif',
    help='The format to save any files in. Defaults to GIF.')
@click.option(
    '-u',
    '--mongo-uri',
    default=helpers.DEFAULT_MONGO_URI,
    help='MongoDB connection string. The database name comes from here too.',
    envvar='DSI_MONGO_URI')
@click.option(
    '--auth-mode',
    'auth_mode',
    default=None,
    type=click.Choice(['keyring', 'prompt']),
    help='How mongodb authentication information is discovered.')
@click.option('--mongo-username', 'mongo_username', help='Username to connect to MongoDB.')
@click.option('--mongo-password', 'mongo_password', help='Password to connect to MongoDB.')
@click.option('-q', '--queryable', default=False, help='Print ids as queries')
@click.option('-n', '--dry-run', is_flag=True, default=False, help='Do not actually run anything.')
@click.option(
    '-c', '--compact/--expanded', 'compact', default=True, help='Display objects one / line.')
@click.option(
    '--style', default=['bmh'], multiple=True, help='The default matplot lib style to use.')
@click.option('--token-file', default=None, envvar='DSI_TOKEN_FILE')
@click.option('--mongo-repo', 'mongo_repo', default='~/src', envvar='DSI_MONGO_REPO')
@click.pass_context
def cli(context, debug, logfile, out, file_format, mongo_uri, auth_mode, mongo_username,
        mongo_password, queryable, dry_run, compact, style, token_file, mongo_repo):
    """ Outliers CLI. """
    # pylint: disable=missing-docstring, too-many-arguments, too-many-locals
    config = helpers.CommandConfiguration(
        debug=debug,
        out=out,
        log_file=logfile,
        file_format=file_format,
        mongo_uri=mongo_uri,
        auth_mode=auth_mode,
        mongo_username=mongo_username,
        mongo_password=mongo_password,
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


cli.add_command(config_command)
cli.add_command(replay_command)
cli.add_command(manage_outliers_command)
cli.add_command(mute_outliers_command)
cli.add_command(unmute_outliers_command)
