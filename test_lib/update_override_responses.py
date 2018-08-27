"""
Used to update the persistent dictionary overrides_responses.
Run from root directory: PYTHONPATH=analysis:bin:. python tests/update_override_responses.py.
"""

import os
import unittest
import shelve
from functools import partial

import requests
from fixture_files import FixtureFiles
from mock import patch
#pylint: disable=unused-import
from tests.test_delete_overrides import TestDeleteOverrides
from tests.test_multi_analysis import TestMultiEvergreenAnalysis
from tests.test_multi_patch_builds import TestMultiEvergreen
from tests.test_override import TestOverride
from tests.test_update_overrides import TestUpdateOverrides
#pylint: enable=unused-import

FIXTURE = FixtureFiles()
RESPONSES_SHELVE = None


def update_persistent_dict(database, url, **kwargs):
    """
    This function is used to replace ContextShelve.get so that requests are made to update the
    persistent dictionary.

    :param dict database: A shelve persistent dictionary. This parameter is assigned with :method:
    `functools.partial`.
    For more details on **url** / kwargs / returns, see :method: `ContextShelve.get`.
    :return: Value at key `url` in `database`.
    """
    response = requests.get(url, **kwargs)
    database[url] = response.json()
    assert database[url] is not None
    return database[url]


def main():
    """
    This function updates the persistent dictionary override_responses with latest data from the
    Evergreen API.

    The captured traffic is written to **override_responses**, see :method:
    `test_utils.fixture_file_path`. This current implementation will try to persist as much as
    possible (even on an exception or signal). But an error case is likely to result in an
    incomplete override_responses file and anything then depends on the overrides file will also
    likely fail (with something like **error: (35, 'Resource temporarily unavailable')**).

    The call to unittest.main is buffered, as a result stdout and stderr are only printed  on
    error.  See `unittest.main cmd options
    <https://docs.python.org/2/library/unittest.html#cmdoption-unittest-b>'.

    If reinstating this code into evergreen-dsitest.yml then the cp calls should look like:
        cp ./tests/unittest-files/override_responses /data/dsitest/override_responses || true
    """
    persistent_dict_path = FIXTURE.fixture_file_path('override_responses')
    persistent_dict_new_path = FIXTURE.fixture_file_path('override_responses.new')
    database = shelve.open(persistent_dict_new_path)
    with patch('tests.test_requests_parent.ContextShelve.get') as mock_get:
        mock_get.side_effect = partial(update_persistent_dict, database)
        unittest.main(exit=False, buffer=True, failfast=True)
        assert mock_get.called is True

    database.close()
    os.rename(persistent_dict_new_path, persistent_dict_path)


if __name__ == '__main__':
    main()
