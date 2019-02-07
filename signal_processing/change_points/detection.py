"""
Change points detection.
"""
from collections import OrderedDict

import numpy as np
import structlog

from analysis.evergreen.helpers import get_githashes_in_range_github, get_githashes_in_range_repo
from signal_processing.change_points.e_divisive import EDivisive
from signal_processing.change_points.range_finder import generate_start_and_end
from signal_processing.change_points.range_finder import link_ordered_change_points

LOG = structlog.getLogger(__name__)

MAJOR_REGRESSION_MAGNITUDE = np.log(1 / np.e**.5)
"""
The magnitude threshold for categorizing a change point as a major regression.
See :method:`_calculate_magnitude` for more details.
"""

MODERATE_REGRESSION_MAGNITUDE = np.log(1 / np.e**.2)
"""
The magnitude threshold for categorizing a change point as a moderate regression.
See :method:`_calculate_magnitude` for more details.
"""

MINOR_REGRESSION_MAGNITUDE = 0
"""
The magnitude threshold for categorizing a change point as a minor regression.
See :method:`_calculate_magnitude` for more details.
"""

MAJOR_IMPROVEMENT_MAGNITUDE = np.log(np.e**.5)
"""
The magnitude threshold for categorizing a change point as a major improvement.
See :method:`_calculate_magnitude` for more details.
"""

MODERATE_IMPROVEMENT_MAGNITUDE = np.log(np.e**.2)
"""
The magnitude threshold for categorizing a change point as a moderate improvement.
See :method:`_calculate_magnitude` for more details.
"""


def detect_change_points(state,
                         pvalue=0.05,
                         permutations=100,
                         weighting=0.001,
                         mongo_repo=None,
                         github_credentials=None):
    # pylint: disable=too-many-arguments
    """
    Run the change points detection algorithm and return the changes points.

    :param dict state: The input data for the calculations. This contains the time series
    performance data ('series') and the meta data (like 'revisions', 'orders', 'create_times' and
    'thread_level') to help identify the location of any calculated change points.
    :param float pvalue: This is the significance level for the testing.
    See 'P-value<https://en.wikipedia.org/wiki/P-value>'.
    :param int permutations: The max number of permutations to perform when evaluating the
    pvalue significance testing.
    :param float weighting: A value used to seed the decay weights array when finding the start
    / end positions of the actual change point.
    :param str mongo_repo: The mongo git repo location.
    :param dict github_credentials: The github token.
    :return: the change points in order of probability.
    :rtype: list(dict)
    """
    algorithm = EDivisive(pvalue, permutations)
    detection = ChangePointsDetection(algorithm, weighting, mongo_repo, github_credentials)
    return detection.detect_change_points(state)


class ChangePointsDetection(object):
    # pylint: disable=too-many-instance-attributes, too-few-public-methods
    """
    The change points detection logic relying on the E-Divisive algorithm.
    """

    def __init__(self, e_divisive, weighting=0.001, mongo_repo=None, github_credentials=None):
        self._e_divisive = e_divisive
        self._weighting = weighting
        self._mongo_repo = mongo_repo
        self._github_credentials = github_credentials

    def detect_change_points(self, state):
        """
        Detect the change points.

        :param dict state: The input data for the calculations. This contains the time series
        performance data ('series') and the meta data (like 'revisions', 'orders', 'create_times'
        and 'thread_level') to help identify the location of any calculated change points.
        :return: the change points in order of probability.
        :rtype: list(dict)
        """
        LOG.info('detect_change_points')
        series = state.get('series')

        e_divisive_change_points = self._e_divisive.compute_change_points(series)
        change_points = self._add_to_change_points(state, e_divisive_change_points, 'E-Divisive')
        LOG.debug("detect_change_points", change_points=change_points)
        return change_points

    def _add_to_change_points(self, state, change_points, algorithm_name):
        # pylint: disable=too-many-locals
        """
        Update raw change points to:
            1) Sort the change point indexes.
            2) Use the sorted change point indexes to get the start end ranges.
            3) Use the start / end ranges to create a list of change points including the ranges.
            4) Calculate descriptive stats from series[prev:start] and series[end:next]
            5) Create change point dicts from this data.

        :param dict state: The input data for the calculations. This contains the time series
        performance data ('series') and the meta data (like 'revisions', 'orders', 'create_times'
        and 'thread_level') to help identify the location of any calculated change points.
        :param list(EDivisiveChangePoint) change_points: The raw change points data.
        :param str algorithm_name: The algorithm name.

        :return: The change points in order of probability.
        :rtype: list(dict).
        """
        series = state.get('series')
        revisions = state.get('revisions')
        orders = state.get('orders')
        create_times = state.get('create_times')
        thread_level = state.get('thread_level')
        points = []
        sorted_indexes = sorted([point.index for point in change_points])
        start_ends = generate_start_and_end(sorted_indexes, series, weighting=self._weighting)
        link_ordered_change_points(start_ends, series)

        for order_of_change_point, point in enumerate(change_points):
            # Find the index of the change point in the range finder output.
            range_index = next(
                i for i, start_end in enumerate(start_ends) if point.index == start_end['index'])
            current_range = start_ends[range_index]

            # Create a dict for the algorithm output. This is saved as a sub-document
            # in the change point.
            algorithm = OrderedDict([('name', algorithm_name)])
            algorithm.update(point._asdict())

            # Get the revision flagged by E-Divisive and add it to the
            # calculations to track.
            algorithm['revision'] = revisions[algorithm['index']]

            # Create a dict fort the range finder state. This is saved as
            # a sub-document in the change point.
            range_finder = OrderedDict([('weighting', self._weighting)]) # yapf: disable

            # Start to colate the information we want to put at the top-level
            # of the change point

            # This represents the last stable revision before the change in
            # performance.
            stable_revision_index = current_range['start']  # oldest
            stable_revision = revisions[stable_revision_index]  # oldest

            # This represents the first githash that displays the change
            # in performance. It may not be the root cause. There may
            # be older unrun revisions (between this and the stable
            # revision).
            # Put this value in the BF first fail or fix revision
            suspect_revision_index = current_range['end']
            suspect_revision = revisions[suspect_revision_index]  # newest

            # The complete set of git hashes between the suspect / newer revision
            # (included in the list) to the stable / older revision (excluded from
            # the list) to the . The order is from newest to oldest
            # so suspect revision is the first element in the list.
            # Any change in performance must be as a result of one of the
            # revisions in this list (assuming the change point is real and
            # as a result of some code change).
            all_suspect_revisions = self._get_git_hashes(stable_revision, suspect_revision)

            magnitude, category = _calculate_magnitude(current_range.get('statistics', {}))

            probability = 1.0 - algorithm['probability']

            point = OrderedDict([('thread_level', thread_level),
                                 ('suspect_revision', suspect_revision),
                                 ('all_suspect_revisions', all_suspect_revisions),
                                 ('probability', probability),
                                 ('create_time', create_times[suspect_revision_index]),
                                 ('value', series[suspect_revision_index]),
                                 ('order', orders[suspect_revision_index]),
                                 ('order_of_change_point', order_of_change_point),
                                 ('statistics', current_range.get('statistics', {})),
                                 ('range_finder', range_finder),
                                 ('algorithm', algorithm),
                                 ('magnitude', magnitude),
                                 ('category', category)]) # yapf: disable
            points.append(point)

            LOG.debug("algorithm output", points=points)

        return points

    def _get_git_hashes(self, older_revision, newer_revision):
        """
        Get git hashes from local git repo or github.

        :param str newer_revision: The newest git hash.
        :param str older_revision: The oldest git hash.
        :return: All the git hashes between older and newer (excluding older). The
        order is from newer to older.
        """
        LOG.debug(
            "getting githashes from repo",
            mongo_repo=self._mongo_repo,
            newer_revision=newer_revision,
            older_revision=older_revision)

        git_hashes = None
        # pylint: disable=bare-except
        try:
            git_hashes = get_githashes_in_range_repo(older_revision, newer_revision,
                                                     self._mongo_repo)
            LOG.debug("githashes from repo", git_hashes=git_hashes)
        except:
            LOG.error("unexpected error on rev-list", exc_info=1)

        if git_hashes is None:
            github_token = None
            if self._github_credentials and 'token' in self._github_credentials:
                github_token = self._github_credentials['token']
            LOG.debug(
                "getting githashes from github",
                mongo_repo=self._mongo_repo,
                token=True if github_token else False,
                newer_revision=newer_revision,
                older_revision=older_revision)
            try:
                git_hashes = [
                    commit['sha']
                    for commit in get_githashes_in_range_github(
                        older_revision, newer_revision, token=github_token, per_page=100)
                ]
                LOG.debug("githashes from github", git_hashes=git_hashes)
            except:
                LOG.error("unexpected error in get git hashes", exc_info=1)
                git_hashes = []
        LOG.debug("loaded git hashes", git_hashes=git_hashes)
        return git_hashes


def _calculate_magnitude(statistics):
    """
    Given a change point, calculate the magnitude. The magnitude is:

        1. log(next_mean / previous_mean) for throughput values
        2. log(previous_mean / next_mean) for latency values.

    :param dict statistics: The statistics to use to calculate the magnitude.
    :return: The magnitude along with a corresponding category.
    :rtype: tuple(float, str).
    """
    if not statistics or not statistics.get('previous', None) or not statistics.get('next', None):
        return None, 'Uncategorized'

    previous_mean = statistics['previous']['mean']
    next_mean = statistics['next']['mean']
    if previous_mean == 0 and next_mean == 0:
        magnitude = 0
    elif previous_mean == 0:
        magnitude = float('inf')
    elif next_mean == 0:
        magnitude = float('-inf')
    elif next_mean >= 0 and previous_mean >= 0:
        magnitude = np.log(float(next_mean) / float(previous_mean))
    else:
        # Currently, the collection and storage of metrics is primitive in that a higher number
        # always means better and lower always means worse. Thus for latencies, we negate the
        # results. This will change with the Expanded Metrics project and so will the means for
        # determining the type of result we are dealing with. In other words, once the project is
        # complete, we should not distinguish a latency metric by its sign; there will be more
        # sophisticated ways of doing so.
        # TODO: PM-965: `Expanded Metrics Collection (Latency, Distribution, Percentiles)`.
        magnitude = np.log(float(previous_mean) / float(next_mean))

    if magnitude < MAJOR_REGRESSION_MAGNITUDE:
        category = 'Major Regression'
    elif magnitude < MODERATE_REGRESSION_MAGNITUDE:
        category = 'Moderate Regression'
    elif magnitude < MINOR_REGRESSION_MAGNITUDE:
        category = 'Minor Regression'
    elif magnitude > MAJOR_IMPROVEMENT_MAGNITUDE:
        category = 'Major Improvement'
    elif magnitude > MODERATE_IMPROVEMENT_MAGNITUDE:
        category = 'Moderate Improvement'
    else:
        category = 'Minor Improvement'

    return magnitude, category