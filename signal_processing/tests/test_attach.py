"""
Unit tests for signal_processing/commands/attach.py.
"""

import unittest

from mock import MagicMock, patch, call

from signal_processing.commands.attach import get_field_value, get_issue_state, REMOTE_KEYS, \
    map_identifiers, attach, detach


class TestGetFieldValue(unittest.TestCase):
    """
    Test get_field_value.
    """

    def test_get_none(self):
        """ Test get_field_value None."""

        mock_build_failure = MagicMock(name='build_failure', key=None)
        self.assertEquals(set(), get_field_value(mock_build_failure, 'key'))

    def test_get_key(self):
        """ Test get_field_value single level."""

        mock_build_failure = MagicMock(name='build_failure', key=['value'])
        self.assertEquals(set(['value']), get_field_value(mock_build_failure, 'key'))

    def test_get_field(self):
        """ Test get_field_value multiple level."""

        mock_build_failure = MagicMock(name='build_failure')
        expected = ['fields', 'values']
        mock_build_failure.fields.customfield_14852 = expected
        self.assertEquals(set(expected), get_field_value(mock_build_failure, 'fix_revision'))


class TestGetIssueState(unittest.TestCase):
    """
    Test get_issue_state.
    """

    def test(self):
        """ Test get_issue_state."""

        with patch('signal_processing.commands.attach.get_field_value') as mock_get_field_value:
            mock_build_failure = MagicMock(name='build_failure', key=None)

            expected = {k: k.upper() for k in REMOTE_KEYS}
            mock_get_field_value.side_effect = [k.upper() for k in REMOTE_KEYS]

            self.assertEquals(expected, get_issue_state(mock_build_failure))
            calls = [call(mock_build_failure, k) for k in REMOTE_KEYS]
            mock_get_field_value.assert_has_calls(calls)


class TestMapIdentifiers(unittest.TestCase):
    """
    Test map_identifiers.
    """

    def test_fix(self):
        """ Test fix."""

        limit = 2
        test_identifiers = [{
            'suspect_revision': 'Fix Revision {}'.format(i),
            'revision': 'Revision {}'.format(i),
            'project': 'sys-perf {}'.format(i),
            'variant': 'linux-standalone {}'.format(i),
            'task': 'bestbuy_agg {}'.format(i),
            'test': 'NetworkBandwith {}'.format(i)
        } for i in range(1, limit)]
        expected = {
            'fix_revision': set(['Fix Revision {}'.format(i) for i in range(1, limit)]),
            'project': set(['sys-perf {}'.format(i) for i in range(1, limit)]),
            'buildvariants': set(['linux-standalone {}'.format(i) for i in range(1, limit)]),
            'tasks': set(['bestbuy_agg {}'.format(i) for i in range(1, limit)]),
            'tests': set(['NetworkBandwith {}'.format(i) for i in range(1, limit)])
        }
        actual = map_identifiers(test_identifiers, True)
        self.assertEquals(expected, actual)

    def test_no_fix(self):
        """ Test no fix."""

        limit = 2
        test_identifiers = [{
            'suspect_revision': 'Fix Revision {}'.format(i),
            'revision': 'Revision {}'.format(i),
            'project': 'sys-perf {}'.format(i),
            'variant': 'linux-standalone {}'.format(i),
            'task': 'bestbuy_agg {}'.format(i),
            'test': 'NetworkBandwith {}'.format(i)
        } for i in range(1, limit)]
        expected = {
            'first_failing_revision': set(['Fix Revision {}'.format(i) for i in range(1, limit)]),
            'project': set(['sys-perf {}'.format(i) for i in range(1, limit)]),
            'buildvariants': set(['linux-standalone {}'.format(i) for i in range(1, limit)]),
            'tasks': set(['bestbuy_agg {}'.format(i) for i in range(1, limit)]),
            'tests': set(['NetworkBandwith {}'.format(i) for i in range(1, limit)])
        }
        actual = map_identifiers(test_identifiers, False)
        self.assertEquals(expected, actual)

    def test_field_name(self):
        """ Test field name."""

        limit = 2
        test_identifiers = [{
            'suspect_revision': 'Fix Revision {}'.format(i),
            'revision': 'Revision {}'.format(i),
            'project': 'sys-perf {}'.format(i),
            'variant': 'linux-standalone {}'.format(i),
            'task': 'bestbuy_agg {}'.format(i),
            'test': 'NetworkBandwith {}'.format(i)
        } for i in range(1, limit)]
        expected = {
            'first_failing_revision': set(['Revision {}'.format(i) for i in range(1, limit)]),
            'project': set(['sys-perf {}'.format(i) for i in range(1, limit)]),
            'buildvariants': set(['linux-standalone {}'.format(i) for i in range(1, limit)]),
            'tasks': set(['bestbuy_agg {}'.format(i) for i in range(1, limit)]),
            'tests': set(['NetworkBandwith {}'.format(i) for i in range(1, limit)])
        }
        actual = map_identifiers(test_identifiers, False, revision_field_name='revision')
        self.assertEquals(expected, actual)

    def test_set(self):
        """ Test set."""

        limit = 2
        test_identifiers = [{
            'suspect_revision': 'Fix Revision {}'.format(i),
            'revision': 'Revision {}'.format(i),
            'project': 'sys-perf {}'.format(i),
            'variant': 'linux-standalone {}'.format(i),
            'task': 'bestbuy_agg {}'.format(i),
            'test': 'NetworkBandwith {}'.format(i)
        } for i in range(1, limit)]
        copy = test_identifiers[0].copy()
        copy['suspect_revision'] = 'Fix Revision {}'.format(limit)

        test_identifiers.append(copy)
        expected = {
            'first_failing_revision':
                set(['Fix Revision {}'.format(i) for i in range(1, limit + 1)]),
            'project':
                set(['sys-perf {}'.format(i) for i in range(1, limit)]),
            'buildvariants':
                set(['linux-standalone {}'.format(i) for i in range(1, limit)]),
            'tasks':
                set(['bestbuy_agg {}'.format(i) for i in range(1, limit)]),
            'tests':
                set(['NetworkBandwith {}'.format(i) for i in range(1, limit)])
        }
        actual = map_identifiers(test_identifiers, False)
        self.assertEquals(expected, actual)


def create_remote_state(limit=2, start=1):
    return {
        'fix_revision': set(['Fix Revision {}'.format(i) for i in range(start, limit)]),
        'first_failing_revision': set(['Revision {}'.format(i) for i in range(start, limit)]),
        'project': set(['sys-perf {}'.format(i) for i in range(start, limit)]),
        'buildvariants': set(['linux-standalone {}'.format(i) for i in range(start, limit)]),
        'tasks': set(['bestbuy_agg {}'.format(i) for i in range(start, limit)]),
        'tests': set(['NetworkBandwith {}'.format(i) for i in range(start, limit)])
    }


class TestAttach(unittest.TestCase):
    """
    Test attach.
    """

    def test_no_identifiers(self):
        """ Test no test identifiers."""

        with patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True) as mock_command_config_cls, \
             patch('signal_processing.change_points.attach.get_issue_state') as mock_get_issue_state:

            mock_build_failure = MagicMock(name='build_failure')
            mock_config = MagicMock(name='config')
            mock_command_config_cls.return_value = mock_config
            test_identifiers = []
            attach(mock_build_failure, test_identifiers, True, mock_config)
            mock_get_issue_state.assert_not_called()

    def _test(self, remote_state, mapped_test_identifiers, expected_fields=None, fix=True):

        with patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True) as mock_command_config_cls, \
             patch('signal_processing.change_points.attach.get_issue_state') as mock_get_issue_state,\
             patch('signal_processing.change_points.attach.map_identifiers') as mock_map_test_identifiers:

            mock_build_failure = MagicMock(name='build_failure')
            mock_config = MagicMock(name='config')
            mock_command_config_cls.return_value = mock_config

            mock_get_issue_state.return_value = remote_state
            mock_map_test_identifiers.return_value = mapped_test_identifiers

            test_identifiers = ['test_identifiers']
            attach(mock_build_failure, test_identifiers, fix, mock_config)
            mock_get_issue_state.assert_called_once_with(mock_build_failure)
            mock_map_test_identifiers.assert_called_once_with(
                test_identifiers, fix, revision_field_name='revision')

            if expected_fields is None:
                mock_build_failure.update.asert_not_called()
            else:
                mock_build_failure.update.asert_called_once_with(fields=expected_fields)

    def test_fix_false(self):
        """ Test fix False."""
        remote_state = create_remote_state()
        mapped_test_identifiers = remote_state
        self._test(remote_state, mapped_test_identifiers, fix=False)

    def test_fix_true(self):
        """ Test fix True."""
        remote_state = create_remote_state()
        mapped_test_identifiers = remote_state
        self._test(remote_state, mapped_test_identifiers)

    def test_super_set(self):
        """ Test where update is super set."""
        remote_state = create_remote_state()
        mock_map_test_identifiers = create_remote_state(limit=3)
        self._test(remote_state, mock_map_test_identifiers, mock_map_test_identifiers)

    def test_additional_set(self):
        """ Test where update is additive."""

        limit = 4
        remote_state = create_remote_state(limit=limit)
        mock_map_test_identifiers = create_remote_state(limit=limit * 2, start=limit)
        expected_fields = create_remote_state(limit=limit * 2)
        self._test(remote_state, mock_map_test_identifiers, expected_fields)


class TestDetach(unittest.TestCase):
    """
    Test detach.
    """

    def test_no_identifiers(self):
        """ Test no test identifiers."""

        with patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True) as mock_command_config_cls, \
             patch('signal_processing.change_points.attach.get_issue_state') as mock_get_issue_state:

            mock_build_failure = MagicMock(name='build_failure')
            mock_config = MagicMock(
                name='config')  #, points=mock_points, debug=0, log_file='/tmp/log_file')
            mock_command_config_cls.return_value = mock_config
            test_identifiers = []
            detach(mock_build_failure, test_identifiers, True, mock_config)
            mock_get_issue_state.assert_not_called()

    def _test(self, remote_state, mapped_test_identifiers, expected_fields=None, fix=True):

        with patch('signal_processing.change_points.helpers.CommandConfiguration', autospec=True) as mock_command_config_cls, \
             patch('signal_processing.change_points.attach.get_issue_state') as mock_get_issue_state,\
             patch('signal_processing.change_points.attach.map_identifiers') as mock_map_test_identifiers:

            mock_build_failure = MagicMock(name='build_failure')
            mock_config = MagicMock(name='config', dry_run=False)
            mock_command_config_cls.return_value = mock_config

            mock_get_issue_state.return_value = remote_state
            mock_map_test_identifiers.return_value = mapped_test_identifiers

            test_identifiers = ['test_identifiers']
            detach(mock_build_failure, test_identifiers, fix, mock_config)
            mock_get_issue_state.assert_called_once_with(mock_build_failure)
            mock_map_test_identifiers.assert_called_once_with(
                test_identifiers, fix, revision_field_name='revision')

            if expected_fields is None:
                mock_build_failure.update.asert_not_called()
            else:
                mock_build_failure.update.asert_called_once_with(fields=expected_fields)

    def test_fix_false(self):
        """ Test fix False."""
        remote_state = create_remote_state()
        expected_fields = create_remote_state(limit=1)
        self._test(remote_state, remote_state, expected_fields=expected_fields, fix=False)

    def test_fix_true(self):
        """ Test fix True."""
        remote_state = create_remote_state()
        expected_fields = create_remote_state(limit=1)
        self._test(remote_state, remote_state, expected_fields=expected_fields)

    def test_super_set(self):
        """ Test where update is super set."""
        remote_state = create_remote_state(limit=3)  # create_remote_state()
        mapped_test_identifiers = create_remote_state()  # create_remote_state(limit=3)
        expected_fields = create_remote_state(limit=3, start=2)  # create_remote_state(limit=3)
        self._test(remote_state, mapped_test_identifiers, expected_fields=expected_fields)

    def test_additional_set(self):
        """ Test where update is additive."""

        limit = 4
        remote_state = create_remote_state(limit=limit * 2)
        mock_map_test_identifiers = create_remote_state(limit=limit + 1, start=limit)

        # remove elements ending in 4 from set
        expected_fields = {
            key: set([value for value in values if value[-1] != str(limit)])
            for key, values in remote_state.items()
        }
        self._test(remote_state, mock_map_test_identifiers, expected_fields=expected_fields)
