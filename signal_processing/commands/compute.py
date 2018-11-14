"""
Functionality to compute / recompute change points.
"""

import structlog

from signal_processing.detect_changes import PointsModel

LOG = structlog.getLogger(__name__)


def compute_change_points(test_identifier, weighting, command_config):
    """
    Compute all the change points for the test identifier.

    :param dict test_identifier: The project, variant, task, test identifier.
    :param float weighting: The weighting on the decay.
    :param CommandConfig command_config: Common configuration.
    :return: The number of points and the change points detected.
    :rtype: dict.
    """
    LOG.debug(
        'computing change points', test_identifier=test_identifier, dry_run=command_config.dry_run)

    points_count = None
    change_points = None
    if not command_config.dry_run:
        mongo_repo = command_config.mongo_repo
        credentials = command_config.credentials
        model = PointsModel(
            command_config.mongo_uri, mongo_repo=mongo_repo, credentials=credentials)
        points_count, change_points = model.compute_change_points(
            test_identifier, weighting=weighting)
        LOG.info(
            "compute",
            test_identifier=test_identifier,
            points_count=points_count,
            change_points=change_points)
    return {'points': points_count, 'change_points': change_points}
