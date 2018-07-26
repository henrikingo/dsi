"""
Functionality to compute / recompute change points.
"""
from collections import OrderedDict
from datetime import timedelta

import structlog

from signal_processing.detect_changes import PointsModel

LOG = structlog.getLogger(__name__)


def compute_change_points(test_identifier, weighting, command_config):
    """
    Compute all the change points for the test identifier.

    :param dict test_identifier: The project, variant, task, test identifier.
    :param float weighting: The weighting on the decay.
    :param CommandConfig command_config: Common configuration.
    """
    LOG.debug(
        'computing change points', test_identifier=test_identifier, dry_run=command_config.dry_run)

    perf_json = OrderedDict([('project_id', test_identifier['project']),
                             ('variant', test_identifier['variant']),
                             ('task_name', test_identifier['task'])]) # yapf: disable
    if not command_config.dry_run:
        mongo_repo = command_config.mongo_repo
        credentials = command_config.credentials
        model = PointsModel(
            perf_json, command_config.mongo_uri, mongo_repo=mongo_repo, credentials=credentials)
        test_name = test_identifier['test']
        points_count, change_points, duration = model.compute_change_points(
            test_name, weighting=weighting)
        LOG.debug(
            "change points",
            points_count=points_count,
            change_points=change_points,
            duration=str(timedelta(milliseconds=duration)))
