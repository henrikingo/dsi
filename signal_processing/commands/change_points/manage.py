"""
Command to create or recreate the unprocessed change points view.
"""

import click
import structlog

from signal_processing.change_points import manage

LOG = structlog.getLogger(__name__)


@click.command(name='manage')
@click.pass_obj
@click.option('--drop', 'drop', is_flag=True, help='Drop indexes before creating them.')
@click.option('--force', 'force', is_flag=True, help='Do not prompt before dropping indexes.')
@click.option(
    '--index',
    'indexes',
    multiple=True,
    type=click.Choice(manage.COLLECTIONS_TO_INDEX),
    help='Collections to create indexes on.')
def manage_command(command_config, drop, force, indexes):
    """
Manage the infrastructural elements of the performance database. That is, indexes,
views etc.

\b
At the moment, it supports:
        1. The unprocessed change points view.
        2. The linked build failures view.
        3. The indexes for the point collection.
"""
    LOG.debug('starting')
    manage.manage(command_config, indexes, drop, force)
