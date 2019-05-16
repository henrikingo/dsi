"""
Unit test for atlas_client.py
"""

import unittest
from mock import patch
import requests

import common.atlas_client as atlas_client


class TestAtlasClient(unittest.TestCase):
    def setUp(self):
        self.api = {
            'root': 'https://cloud-dev.mongodb.com/api/atlas/v1.0/MOCK/URL',
            'group_id': 'mock_group_id'
        }
        self.api_credentials = {'user': 'mock_user', 'key': 'mock_key'}
        self.auth = requests.auth.HTTPDigestAuth('mock_user', 'mock_key')
        self.atlas_client = atlas_client.AtlasClient(self.api, self.api_credentials)

    @patch('requests.post')
    def test_create_cluster(self, mock_post):
        self.atlas_client.create_cluster({'mock_cluster': 'omitting_config'})
        mock_post.assert_called_with(
            self.api['root'] + '/groups/mock_group_id/clusters',
            auth=self.auth,
            json={
                'mock_cluster': 'omitting_config'
            })

    @patch('requests.delete')
    def test_delete_cluster(self, mock_delete):
        self.atlas_client.delete_cluster('test_cluster_name')
        mock_delete.assert_called_with(
            self.api['root'] + '/groups/mock_group_id/clusters/test_cluster_name', auth=self.auth)

    @patch('requests.get')
    def test_get_one_cluster(self, mock_get):
        self.atlas_client.get_one_cluster('test_cluster_name')
        mock_get.assert_called_with(
            self.api['root'] + '/groups/mock_group_id/clusters/test_cluster_name', auth=self.auth)

    @patch('time.sleep')
    @patch('common.atlas_client.AtlasClient.get_one_cluster')
    def test_await(self, mock_get_one_cluster, mock_time):
        state_names = [{'stateName': 'CREATING'}, {'stateName': 'CREATING'}, {'stateName': 'IDLE'}]
        # Note: When given an iterable, side_effect returns one element for each call.
        mock_get_one_cluster.side_effect = state_names

        self.atlas_client.await('test_cluster_name')
        mock_get_one_cluster.assert_called_with('test_cluster_name')
        mock_time.assert_called()
