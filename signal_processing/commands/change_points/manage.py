"""
Command to create or recreate the unprocessed change points view.
"""

import click
import structlog

from signal_processing.change_points import manage

LOG = structlog.getLogger(__name__)


@click.command(name='manage')
@click.pass_obj
def manage_command(command_config):
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
    manage.manage(command_config)
