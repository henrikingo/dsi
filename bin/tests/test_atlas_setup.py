"""
Unit test for atlas_setup.py
"""
import copy
import logging
import unittest
import os

from mock import patch, MagicMock, ANY
from testfixtures import LogCapture

import common.atlas_setup as atlas_setup
# Note that below functions only work because test_config.py is in the same directory as this file.
from test_config import load_config_dict, in_dir
from test_lib.fixture_files import FixtureFiles
import test_lib.structlog_for_test as structlog_for_test

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


class TestAtlasSetup(unittest.TestCase):
    def _cleanup(self):
        if os.path.exists(self.out_file):
            os.remove(self.out_file)
        if os.path.exists(self.coverage_file):
            os.remove(self.coverage_file)

    def setUp(self):
        self.out_file = os.path.join(
            FIXTURE_FILES.fixture_file_path('atlas-config'), 'mongodb_setup.out.yml')
        self.coverage_file = os.path.join(
            FIXTURE_FILES.fixture_file_path('atlas-config'), 'coverage.xml')
        self._cleanup()
        structlog_for_test.setup_logging()

    def tearDown(self):
        self._cleanup()

    @patch('common.atlas_client.AtlasClient.get_one_cluster')
    @patch('common.atlas_setup.AtlasSetup._generate_unique_name')
    @patch('requests.post')
    def test_start(self, mock_post, mock_generate, mock_get_one_cluster):
        mock_generate.return_value = 'mock_unique_name'
        response = MagicMock(name='requests.response', autospec=True)
        response.json.return_value = {'name': 'mock_unique_name'}
        mock_post.return_value = response

        mock_http_return_value = {
            'stateName': 'IDLE',
            'name': 'mock_unique_name',
            'mongoURI': 'mongodb://mock_mongo_uri:21017',
            'mongoURIWithOptions': 'mongodb://mock_mongo_uri:21017/?ssl=true&authSource=admin',
            'mongoURIUpdated': '2018-11-27T12:24:17Z'
        }
        mock_get_one_cluster.return_value = mock_http_return_value
        expected_out = copy.deepcopy(mock_http_return_value)
        expected_out.update({
            'hosts': 'mock_mongo_uri:21017',
            'mongodb_url': 'mock_mongo_uri:21017/?ssl=true&authSource=admin'
        })

        with in_dir(FIXTURE_FILES.fixture_file_path('atlas-config')):
            config = load_config_dict('mongodb_setup')
            atlas = atlas_setup.AtlasSetup(config)
            atlas.start()
        mock_post.assert_called()
        self.assertDictEqual(config['mongodb_setup']['out']['atlas']['clusters'][0].as_dict(),
                             expected_out)
        self.assertEquals(len(config['mongodb_setup']['out']['atlas']['clusters']), 1)

    def test_start_when_cluster_exists(self):
        with in_dir(FIXTURE_FILES.fixture_file_path('atlas-config')):
            config = load_config_dict('mongodb_setup')
            # Inject a fake cluster into mongodb_setup.out
            config['mongodb_setup']['out'] = {}
            config['mongodb_setup']['out']['atlas'] = {}
            config['mongodb_setup']['out']['atlas']['clusters'] = [{
                'name': 'some_other_unique_name',
                'stateName': 'IDLE'
            }]
            atlas = atlas_setup.AtlasSetup(config)
            with LogCapture(level=logging.ERROR) as log_error:
                self.assertFalse(atlas.start())
                log_error.check(
                    ('common.atlas_setup', 'ERROR',
                     u'[error    ] Clusters already exist in mongodb_setup.out.atlas.clusters. [common.atlas_setup] '),
                    ('common.atlas_setup', 'ERROR',
                     u'[error    ] Please shutdown existing clusters first with infrastructure_teardown.py. [common.atlas_setup] '
                    )) #yapf: disable

    @patch('common.atlas_client.AtlasClient.get_one_cluster')
    @patch('common.atlas_setup.AtlasSetup._generate_unique_name')
    @patch('requests.delete')
    def test_destroy(self, mock_delete, mock_generate, mock_get_one_cluster):
        with in_dir(FIXTURE_FILES.fixture_file_path('atlas-config')):
            config = load_config_dict('mongodb_setup')
            # Inject a fake cluster into mongodb_setup.out
            config['mongodb_setup']['out'] = {}
            config['mongodb_setup']['out']['atlas'] = {}
            config['mongodb_setup']['out']['atlas']['clusters'] = [{
                'name': 'some_other_unique_name',
                'stateName': 'IDLE'
            }]
            atlas = atlas_setup.AtlasSetup(config)
            atlas.destroy()
        mock_delete.assert_called_with(
            'https://cloud-dev.mongodb.com/api/atlas/v1.0/MOCK/URL/groups/test_group_id/clusters/some_other_unique_name',
            auth=ANY)
        self.assertEquals(config['mongodb_setup']['out']['atlas']['clusters'], [])

    def test_unique_name(self):
        atlas_cluster = {'clusterType': 'REPLSET', 'providerSettings': {'instanceSizeName': 'M99'}}
        with in_dir(FIXTURE_FILES.fixture_file_path('atlas-config')):
            config = load_config_dict('mongodb_setup')
            atlas = atlas_setup.AtlasSetup(config)
            name = atlas._generate_unique_name(atlas_cluster)
        # Generated name looks like: dsi-M99-abcdefg
        # (The last part is random, but fixed length.)
        self.assertRegexpMatches(name, 'dsi-M99-')
        self.assertEquals(len(name), 15)
