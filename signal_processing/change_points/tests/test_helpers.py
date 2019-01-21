"""
Unit tests for signal_processing/change_points/helpers.py.
"""
import unittest

from bin.common.log import setup_logging
from mock import MagicMock

from signal_processing.change_points.helpers import generate_change_point_ranges

setup_logging(False)


# pylint: disable=invalid-name
class TestGenerateChangePointRanges(unittest.TestCase):
    """ Test generate_change_point_ranges. """

    def _test(self, orders=None, change_points=None, change_points_indexes=None):
        """ test change_points_indexes [-1]."""
        test_identifier = dict(project='project')
        mock_model = MagicMock(name='model')
        if orders is None:
            orders = []
        if change_points is None:
            change_points = []
        if change_points_indexes is None:
            change_points_indexes = []
        mock_model.get_points.return_value = dict(orders=orders)
        mock_model.db.__getitem__.return_value.find.return_value.sort.return_value = change_points
        mock_model.db.__getitem__.return_value.find.return_value.sort.return_value = change_points
        return list(
            generate_change_point_ranges(test_identifier, mock_model, change_points_indexes))

    def test_each_no_data(self):
        """ test indexes with no data."""
        ranges = self._test(change_points_indexes=[-1, -2, -3, -4, 0])
        self.assertEquals(ranges, [])

    def test_all_no_data(self):
        """ test all with no data."""
        ranges = self._test()
        self.assertEquals(ranges, [])

    def test_each_no_valid_no_data(self):
        """ test indexes with no valid data."""
        ranges = self._test(orders=range(12), change_points_indexes=[1, -2])
        self.assertEquals(ranges, [])

    def test_all_no_change_points(self):
        """ test all no change points."""
        ranges = self._test(orders=range(2))
        self.assertEquals(ranges, [(0, 1)])

    def test_all_one_change_points(self):
        """ test all one change points."""
        ranges = self._test(orders=range(3), change_points=[dict(order=1)])
        self.assertEquals(ranges, [(0, 1), (1, 2)])

    def _test_three_change_points(self, orders=None, change_points=None,
                                  change_points_indexes=None):
        """ test helper with 3 change points."""
        if change_points is None:
            change_points = [dict(order=3), dict(order=6), dict(order=9)]
            if orders is None:
                orders = range(12)
        return self._test(orders, change_points, change_points_indexes)

    def test_all_three_change_points(self):
        """ test all 3 change points."""
        ranges = self._test_three_change_points()
        self.assertEquals(ranges, [(0, 3), (3, 6), (6, 9), (9, 11)])

    def test_each_one_change_point_backwards(self):
        """ test each with negative index."""
        ranges = self._test_three_change_points(change_points_indexes=[-1])
        self.assertEquals(ranges, [(9, 11)])

    def test_each_one_change_point_forwards(self):
        """ test each with positive index."""
        ranges = self._test_three_change_points(change_points_indexes=[3])
        self.assertEquals(ranges, [(9, 11)])

    def test_each_two_change_point_backwards(self):
        """ test each 2 negative indexes."""
        ranges = self._test_three_change_points(change_points_indexes=[-1, -2])
        self.assertEquals(ranges, [(9, 11), (6, 9)])

    def test_each_two_change_point_forwards(self):
        """ test each 2 positive indexes."""
        ranges = self._test_three_change_points(change_points_indexes=[2, 3])
        self.assertEquals(ranges, [(6, 9), (9, 11)])

    def test_each_three_change_point_backwards(self):
        """ test each 3 negative indexes."""
        ranges = self._test_three_change_points(change_points_indexes=[-1, -2, -3])
        self.assertEquals(ranges, [(9, 11), (6, 9), (3, 6)])

    def test_each_three_change_point_forwards(self):
        """ test each 3 positive indexes."""
        ranges = self._test_three_change_points(change_points_indexes=[1, 2, 3])
        self.assertEquals(ranges, [(3, 6), (6, 9), (9, 11)])

    def test_each_change_point_backwards(self):
        """ test each 4 negative indexes."""
        ranges = self._test_three_change_points(change_points_indexes=[-1, -2, -3, -4])
        self.assertEquals(ranges, [(9, 11), (6, 9), (3, 6), (0, 3)])

    def test_each_change_point_forward(self):
        """ test each 4 positive indexes."""
        ranges = self._test_three_change_points(change_points_indexes=[0, 1, 2, 3, 4])
        self.assertEquals(ranges, [(0, 3), (3, 6), (6, 9), (9, 11)])

    def test_each_too_many_forward(self):
        """ test each too many negative indexes."""
        ranges = self._test_three_change_points(change_points_indexes=[-1, -2, -3, -4, -5])
        self.assertEquals(ranges, [(9, 11), (6, 9), (3, 6), (0, 3)])

    def test_too_many_forward(self):
        """ test each too many positive indexes."""
        ranges = self._test_three_change_points(change_points_indexes=[0, 1, 2, 3, 4])
        self.assertEquals(ranges, [(0, 3), (3, 6), (6, 9), (9, 11)])

    def test_each_no_change_points(self):
        """ test each no change points."""
        ranges = self._test(orders=range(12), change_points_indexes=[-1, -2, -3, -4, -5])
        self.assertEquals(ranges, [(0, 11)])

    def test_each_no_change_points_repeat(self):
        """ test each no change points repeated."""
        ranges = self._test(orders=range(12), change_points_indexes=[-1, -2, -3, -4, 0])
        self.assertEquals(ranges, [(0, 11)])

    def test_each_duplicates(self):
        """ test each duplicates."""
        ranges = self._test_three_change_points(change_points_indexes=[0, 0])
        self.assertEquals(ranges, [(0, 3)])

    def test_each_duplicates_negative(self):
        """ test each duplicates negative."""
        ranges = self._test_three_change_points(change_points_indexes=[0, -4])
        self.assertEquals(ranges, [(0, 3)])

    def test_each_duplicates_negative_ordered(self):
        """ test each duplicates negative check order."""
        ranges = self._test_three_change_points(change_points_indexes=[0, 1, -4, -3])
        self.assertEquals(ranges, [(0, 3), (3, 6)])
