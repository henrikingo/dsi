"""
Command to manage outlier collections.
"""

import click
import structlog

from signal_processing.outliers import manage

LOG = structlog.getLogger(__name__)


@click.command(name='manage')
@click.pass_obj
def manage_outliers_command(command_config):
    """
Manage the infrastructural elements of the outliers collections. That is, indexes,
views etc.
 \b
At the moment, it supports:
        1. The indexes for the outliers collection.
"""
    LOG.debug('starting')
    manage.manage(command_config)
