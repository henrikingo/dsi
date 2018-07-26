"""
Unit tests for signal_processing/compute.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import patch, MagicMock

from signal_processing.commands.compute import compute_change_points

setup_logging(False)


class TestCompute(unittest.TestCase):
    """
    Test suite for compute_change_points method.
    """

    @patch('signal_processing.commands.compute.PointsModel', autospec=True)
    def test_dry_run(self, mock_model):
        """ Test dry run."""
        test_identifier = {
            'project': 'project',
            'variant': 'variant',
            'task': 'task',
            'test': 'test'
        }
        mock_config = MagicMock(
            name='config', dry_run=True, mongo_repo='mongo_repo', credentials=None)

        compute_change_points(test_identifier, .1, mock_config)

        mock_model.assert_not_called()

    @patch('signal_processing.commands.compute.PointsModel', autospec=True)
    def test_compute_with_credentials(self, mock_model):
        """ Test compute with credentials."""
        test_identifier = {
            'project': 'project',
            'variant': 'variant_name',
            'task': 'task',
            'test': 'test'
        }
        credentials = {'credentials': 'credentials'}
        mock_config = MagicMock(
            name='config',
            dry_run=False,
            mongo_uri='mongo_uri',
            mongo_repo='mongo_repo',
            credentials=credentials)

        mock_model_instance = mock_model.return_value
        mock_model_instance.compute_change_points.return_value = (1, [1], 2)
        compute_change_points(test_identifier, .1, mock_config)

        perf_json = {'project_id': 'project', 'variant': 'variant_name', 'task_name': 'task'}
        mock_model.assert_called_once_with(
            perf_json, 'mongo_uri', mongo_repo='mongo_repo', credentials=credentials)
        mock_model_instance.compute_change_points.assert_called_once_with('test', weighting=.1)
