"""
Used to update the persistent dictionary overrides_responses
Run from root directory:
PYTHONPATH=analysis:bin:. python tests/update_override_responses.py
"""
import os
import unittest
import shelve
from mock import patch
import requests
#pylint: disable=unused-import
from tests.test_delete_overrides import TestDeleteOverrides
from tests.test_update_overrides import TestUpdateOverrides
from tests.test_override import TestOverride
from tests.test_multi_analysis import TestMultiEvergreenAnalysis
from tests.test_multi_patch_builds import TestMultiEvergreen
#pylint: enable=unused-import
from tests import test_utils

RESPONSES_SHELVE = None

def main():
    """
    This function updates the persistent dictionary
    override_responses with latest data from the Evergreen API
    """
    persistent_dict_path = test_utils.fixture_file_path('override_responses')
    persistent_dict_new_path = test_utils.fixture_file_path('override_responses.new')
    #pylint: disable=global-statement
    global RESPONSES_SHELVE
    RESPONSES_SHELVE = shelve.open(persistent_dict_new_path)
    with patch('tests.test_requests_parent.ContextShelve.get') as mock_get:
        mock_get.side_effect = update_persistent_dict
        unittest.main(exit=False)
        assert mock_get.called is True
    os.rename(persistent_dict_new_path, persistent_dict_path)

def update_persistent_dict(url, **kwargs):
    """
    This function is used to replace ContextShelve.get so that
    requests are made to update the persistent dictionary
    """
    response = requests.get(url, **kwargs)
    RESPONSES_SHELVE[url] = response.json()
    assert RESPONSES_SHELVE[url] != None
    return RESPONSES_SHELVE[url]

if __name__ == '__main__':
    main()
