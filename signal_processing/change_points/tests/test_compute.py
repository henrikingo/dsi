"""
Unit tests for signal_processing/change_points/compute.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import patch, MagicMock

from signal_processing.change_points import compute

setup_logging(False)

NS = 'signal_processing.change_points.compute'


def ns(relative_name):  # pylint: disable=invalid-name
    """Return a full name from a name relative to the tested module's name space."""
    return NS + '.' + relative_name


class TestCompute(unittest.TestCase):
    """
    Test suite for compute_change_points method.
    """

    @patch(ns('PointsModel'), autospec=True)
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

        compute.compute_change_points(test_identifier, .1, mock_config)

        mock_model.assert_not_called()

    def _test_compute_with_credentials(self, min_points=None):
        with patch(ns('PointsModel'), autospec=True) as mock_model:
            test_identifier = {
                'project': 'project',
                'variant': 'variant_name',
                'task': 'task',
                'test': 'test',
                'thread_level': '1',
            }
            credentials = {'credentials': 'credentials'}
            mock_config = MagicMock(
                name='config',
                dry_run=False,
                mongo_uri='mongo_uri',
                mongo_repo='mongo_repo',
                credentials=credentials)

            mock_model_instance = mock_model.return_value
            mock_model_instance.compute_change_points.return_value = (1, [1])
            compute.compute_change_points(test_identifier, .1, mock_config, min_points=min_points)

            mock_model.assert_called_once_with(
                'mongo_uri', min_points, mongo_repo='mongo_repo', credentials=credentials)
            mock_model_instance.compute_change_points.assert_called_once_with(
                test_identifier, weighting=.1)

    def test_compute_with_credentials(self):
        """ Test compute with credentials."""
        self._test_compute_with_credentials()

    def test_compute_with_limit(self):
        """ Test compute with credentials."""
        self._test_compute_with_credentials(10)