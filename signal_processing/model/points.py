"""
Class to hold points state and business logic.
"""
import sys
import numpy as np

import pymongo
import structlog
from tenacity import retry, stop_after_attempt, wait_fixed

from signal_processing.change_points.detection import detect_change_points

from signal_processing.commands import helpers

LOG = structlog.getLogger(__name__)

REQUIRED_KEYS = {'revision', 'order', 'create_time'}
"""
The set of keys that a valid performance point must in include.
"""

ARRAY_FIELDS = {'series', 'revisions', 'orders', 'create_times', 'task_ids', 'version_ids',\
                'outlier', 'marked', 'rejected', 'whitelisted', }
"""
The set of array field keys. These arrays must be equal in size.
"""


def get_points_aggregation(test_identifier, min_order):
    """
    Get the aggregation pipeline required to get the points data.

    :param dict test_identifier: The project / variant / task / test and thread_level.
    :param int min_order: If given then get all data greater than this value. Otherwise get
    all data.
    :type min_order: int or None.
    :return: The number of points (and thus the length of the lists), the query used to
    retrieve the points and a dict of lists for the metrics for each point (ops/s, revisions,
    orders, create_times, task_ids).
    :rtype: tuple(int, OrderedDict, dict).
    """

    max_thread_level = helpers.is_max_thread_level(test_identifier)
    pipeline = []

    # Step: Match test identifier and correct thread level.
    query = helpers.get_query_for_points(test_identifier)
    # If order was given, only get points after that point.
    if min_order is not None:
        query['order'] = {'$gt': min_order}

    pipeline.append({'$match': query})

    # Step: A valid document must contain values for REQUIRED_KEYS.
    pipeline.append({'$match': {'$and': [{key: {'$ne': None}} for key in REQUIRED_KEYS]}})

    # Step: Sort by order.
    pipeline.append({'$sort': {'order': pymongo.ASCENDING}})

    # Step: Project fields to ensure we only have the required fields.
    # For non-max thread level, this removes results that don't match the correct thread level.
    # No outlier_status field implies a pass status, but we project a null value into the
    # the docs to allow for this case.
    filter_thread_level = {
        'project': 1,
        'revision': 1,
        'variant': 1,
        'task': 1,
        'test': 1,
        'order': 1,
        'create_time': 1,
        'task_id': 1,
        'version_id': 1,
        'test_identifier': test_identifier
    }
    if max_thread_level:
        # The max_ops_per_sec is the correct value.
        filter_thread_level['max_ops_per_sec'] = 1
        filter_thread_level['rejected'] = {'$ifNull': ['$rejected', None]}
        filter_thread_level['outlier'] = {'$ifNull': ['$outlier', None]}
    else:
        # Remove results not matching the correct thread level.
        filter_thread_level['results'] = {
            '$filter': {
                'input': '$results',
                'as': 'result',
                'cond': {
                    '$eq': ['$$result.thread_level', test_identifier['thread_level']]
                }
            }
        }
    pipeline.append({'$project': filter_thread_level})

    # Step: lookup whitelist.
    pipeline.append({
        '$lookup': {
            'from':
                'whitelisted_outlier_tasks',
            'let': {
                'project': '$project',
                'variant': '$variant',
                'task': '$task',
                'revision': '$revision',
                'order': '$order'
            },
            'pipeline': [{
                '$match': {
                    '$expr': {
                        '$and': [
                            {
                                '$eq': ['$project', '$$project']
                            },
                            {
                                '$eq': ['$variant', '$$variant']
                            },
                            {
                                '$eq': ['$task', '$$task']
                            },
                            {
                                '$eq': ['$revision', '$$revision']
                            },
                            {
                                '$eq': ['$order', '$$order']
                            },
                        ]
                    }
                },
            }],
            'as':
                'whitelisted'
        }
    })

    # Step: lookup marked.
    pipeline.append({
        '$lookup': {
            'from':
                'marked_outliers',
            'let': {
                'project': '$project',
                'variant': '$variant',
                'task': '$task',
                'test': '$test',
                'thread_level': '$thread_level',
                'revision': '$revision',
                'order': '$order'
            },
            'pipeline': [{
                '$match': {
                    '$expr': {
                        '$and': [
                            {
                                '$eq': ['$project', '$$project']
                            },
                            {
                                '$eq': ['$variant', '$$variant']
                            },
                            {
                                '$eq': ['$task', '$$task']
                            },
                            {
                                '$eq': ['$test', '$$test']
                            },
                            {
                                '$eq': ['$thread_level', '$$thread_level']
                            },
                            {
                                '$eq': ['$revision', '$$revision']
                            },
                            {
                                '$eq': ['$order', '$$order']
                            },
                        ]
                    }
                },
            }],
            'as':
                'marked'
        }
    })

    # Step: Group by project / variant / task  / test and thread level and simultaneously
    # accumulate the data required for change point detection.
    whitelisted = {'$gte': [{'$size': '$whitelisted'}, 1]}
    marked = {'$eq': ['$marked', None]}
    if max_thread_level:
        # Push max_ops_per_sec to series.
        ops_per_sec = '$max_ops_per_sec'
        rejected = '$rejected'
        outlier = '$outlier'
    else:
        # Push the first results.ops_per_sec. There can only be one.
        ops_per_sec = {'$arrayElemAt': ['$results.ops_per_sec', 0]}
        rejected = {'$ifNull': [{'$arrayElemAt': ['$results.rejected', 0]}, None]}
        outlier = {'$ifNull': [{'$arrayElemAt': ['$results.outlier', 0]}, None]}

    pipeline.append({
        '$group': {
            '_id': None,
            "test_identifier": {
                "$first": "$test_identifier"
            },
            'size': {
                '$sum': 1
            },
            'revisions': {
                '$push': '$revision'
            },
            'series': {
                '$push': ops_per_sec
            },
            'orders': {
                '$push': '$order'
            },
            'create_times': {
                '$push': '$create_time'
            },
            'task_ids': {
                '$push': '$task_id'
            },
            'version_ids': {
                '$push': '$version_id'
            },
            'rejected': {
                '$push': rejected
            },
            'outlier': {
                '$push': outlier
            },
            'whitelisted': {
                '$push': whitelisted
            },
            'marked': {
                '$push': marked
            }
        }
    })
    return pipeline


class PointsModel(object):
    """
    Model that gathers the point data and runs E-Divisive to find change points.
    """

    # pylint: disable=invalid-name, too-many-instance-attributes
    def __init__(self, mongo_uri, min_points=None, pvalue=None, mongo_repo=None, credentials=None):
        # pylint: disable=too-many-arguments
        """
        PointsModel is serializable through pickle. To maintain a consistent stable interface, it
        delegates configuration to __setstate__.
        See methods '__getstate__' and '__setstate__'.

        min_points specifies the minimum number of points used when detecting change points for
        a given test_identifier (that is the project/ variant / task / test and thread_level).

        The approach taken to find the actual number of points is:
        * If min_points is None or 0
          return None (all points).
        * If there are no change points:
           * if min_points > 0
                return None (all points).
           * if min_points < 0
                if abs(min_points) < len(points)
                    return point[abs(min_points)]
                else:
                    return None (all points)
        * If there are change points:
           For each change point from newest (order is highest) to oldest:
              calculate the number of data points between newest point and current change point
            Find the first change point where the sum is greater than min_points and return the
            point associated with this change point.

        The point found is excluded from the change point detection. That is, we calculate change
        points for all points newer than the selected point.

        Note: The latest data point will never have a change point generated for it, so a
        min_points of 1 will always regenerate from the latest change point (if there is one) or
        all if there are none.

        :param str mongo_uri: The uri to connect to the cluster.
        :param min_points: The minimum number of points to consider when detecting change points.
        None or 0 implies no minimum.
        :type min_points: int or None.
        :param pvalue: The pvalue for the E-Divisive algorithm.
        :type pvalue: int, float, None.
        :param mongo_repo: The mongo git location.
        :param credentials: The git credentials.
        """
        self.__setstate__({
            'mongo_uri': mongo_uri,
            'min_points': min_points,
            'pvalue': pvalue,
            'mongo_repo': mongo_repo,
            'credentials': credentials
        })

    # pylint: disable=attribute-defined-outside-init
    @property
    def db(self):
        """
        Getter for self._db.
        """
        if self._db is None:
            self._db = pymongo.MongoClient(self.mongo_uri).get_database()
        return self._db

    def get_points(self, test_identifier, min_order):
        """
        Retrieve the documents from the `points` collection in the database for the given test.

        :param dict test_identifier: The project / variant / task / test and thread_level.
        :param int min_order: If given then get all data greater than this value. Otherwise get
        all data.
        :type min_order: int or None.
        :return: The number of points (and thus the length of the lists), the query used to
        retrieve the points and a dict of lists for the metrics for each point (ops/s, revisions,
        orders, create_times, task_ids).
        :rtype: tuple(int, OrderedDict, dict).
        """

        pipeline = get_points_aggregation(test_identifier, min_order)
        results = list(self.db.points.aggregate(pipeline))[0]
        results.update(test_identifier)
        if '_id' in results:
            del results['_id']

        sizes = {key: len(results[key]) for key in ARRAY_FIELDS}
        if not all(current == sizes.values()[0] for current in sizes.values()):
            raise Exception('All array sizes were not equal: {}'.format(sizes))

        return results

    def _get_closest_order_for_change_points(self, change_point_orders, test_identifier):
        """
        Find an order value greater than or equal to the min_size value and a change point.

        :param list(int) change_point_orders: The list of change point orders. order is an
        incrementing sequence generated by evergreen for each commit. Higher order values represent
        newer revisions.
        :param dict test_identifier: The project / variant / task / test and thread level values.
        :return: The order closest to the min_size or None.
        :rtype: int or None.
        """
        points_query = helpers.get_query_for_points(test_identifier)

        # Get the orders for each change point. The first and last points
        # cannot be change points so add these orders to the array. orders are positive,
        # incrementing values.
        #
        # If there are points outside the boundaries then '$bucket' will create an 'other' bucket.
        # This could cause issues so we prepend (0 is the minimum bound) and append (maxint is the
        # upper, it avoids a query / sort / limit 1) values guaranteed to correctly
        # encapsulate the range boundaries and ensure no 'other' bucket.
        order_boundaries = [0]
        order_boundaries.extend(change_point_orders)
        order_boundaries.append(sys.maxint)

        # Using the orders as boundaries, count the number of points in the buckets for the
        # change points.
        #
        # A change point cannot be generated at the start position (order_boundaries[0]) so this
        # boundary is guaranteed to be there and have a non-zero count. The latest change point
        # (order_boundaries[-1]) will include up any newer data points.
        buckets = list(
            self.db.points.aggregate([{
                '$match': points_query
            }, {
                '$bucket': {
                    'groupBy': "$order",
                    'boundaries': order_boundaries,
                    'default': "Other",
                    'output': {
                        'count': {
                            '$sum': 1
                        }
                    }
                }
            }]))

        # There were change points so there must be bucketed data.
        # find the boundary greater than or equal to min_points.
        buckets.reverse()
        cumsum = np.cumsum([bucket['count'] for bucket in buckets])

        min_points = abs(self.min_points)

        # np.where returns a tuple of (indexes, np.type).
        indexes = np.where(cumsum >= min_points)[0]
        if indexes.size:
            index = indexes[0]
            found = buckets[index]

            # This check is required for the case where the limit is beyond the oldest change
            # point.
            # In this case,_id would be expected to be 0 (or whatever order_boundaries[0] is).
            # Since we are rounding up, we fall through and return None for the sake of
            # consistency.
            if found['_id'] in change_point_orders:
                return found['_id']

        return None

    def _get_closest_order_no_change_points(self, test_identifier):
        """
        There are no change points  so find an order value closest to the min_size value.

        If min_size is None or greater than equal to 0 then return None. This is a new data stream
        and we should generate change points for all data or there are no change points and the
        calculation will be quick anyway.

        If there is no data or abs(min_size) is less than count then return None to select all data
        points.

        Finally, min_size is negative and there is enough data, so get the order value for that
        point. In this case there are no change points so, this is ok.

        :param dict test_identifier: The project / variant / task / test and thread level values.
        :return: The order closest to the min_size or None.
        :rtype: int or None.
        """
        if self.min_points is None or self.min_points >= 0:
            return None

        points_query = helpers.get_query_for_points(test_identifier)
        count = self.db.points.count(points_query)
        min_points = abs(self.min_points)

        if count == 0 or min_points > count:
            return None

        # min_size is less than zero and there are enough performance data points to
        # get the exact value.
        cursor = self.db.points.find(points_query, {
            'order': 1
        }).sort('order', pymongo.DESCENDING).skip(min_points - 1).limit(1)
        points = list(cursor)

        return points[0]['order']

    def get_closest_order(self, test_identifier):
        """
        Find an order value closest to the min_size value and a change point.

        :param dict test_identifier: The project / variant / task / test and thread_level.
        :return: The order closest to the min_size or None.
        :rtype: int or None.
        """
        if self.min_points is None or self.min_points == 0:
            return None

        cursor = self.db.change_points.find(test_identifier, {
            'order': 1
        }).sort('order', pymongo.ASCENDING)
        change_point_orders = [change_point['order'] for change_point in cursor]

        if change_point_orders:
            return self._get_closest_order_for_change_points(change_point_orders, test_identifier)
        return self._get_closest_order_no_change_points(test_identifier)

    def _find_previous_change_point(self, test_identifier, current):
        """
        Get the change point before current.

        :param dict test_identifier: The test identifier.
        :param dict current:  The current change point.
        :return: The previous change point or None.
        :rtype: dict or None.
        """
        change_point_query = test_identifier.copy()
        change_point_query['order'] = {'$lt': current['order']}
        previous_change_point = list(
            self.db.change_points.find(change_point_query).sort('order',
                                                                pymongo.DESCENDING).limit(1))

        if previous_change_point:
            return previous_change_point[0]
        return None

    def _prepare_update_previous_change_point(self, test_identifier, change_point):
        """
        Prepare an update of the statistics of the previous point.

        :param dict test_identifier: The test identifier.
        :param dict change_point: The current change point.
        :return: The previous change point or None.
        :rtype: dict or None.
        """
        previous = self._find_previous_change_point(test_identifier, change_point)

        if previous is not None:
            previous_change_point_query = test_identifier.copy()
            previous_change_point_query['order'] = previous['order']
            statistics = change_point['statistics']['previous']
            return pymongo.UpdateOne(previous_change_point_query, {
                '$set': {
                    'statistics.next': statistics
                }
            })
        return None

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(5))
    def compute_change_points(self, test_identifier, weighting):
        """
        Compute the change points for the given test using the E-Divisive algorithm and insert them
        into the `change_points` collection of the database.

        :param dict test_identifier: The project / variant / task / test and thread_level.
        :param float weighting: The weighting for the decay on compute.
        :return: The number of points for the test, the number of change points found by the
        E-Divisive algorithm, and the time taken for this method to run.
        :rtype: tuple(int, int, float).
        See 'weights.DEFAULT_WEIGHTING' for the recommended default value.
        """
        # pylint: disable=too-many-locals
        order = self.get_closest_order(test_identifier)
        thread_level_results = self.get_points(test_identifier, order)

        change_points = detect_change_points(
            thread_level_results,
            pvalue=self.pvalue,
            weighting=weighting,
            mongo_repo=self.mongo_repo,
            github_credentials=self.credentials)
        change_points = sorted(change_points, key=lambda k: k['order'])

        LOG.debug(
            "compute_change_points starting",
            change_points=len(change_points),
            test_identifier=test_identifier)

        query = test_identifier

        if order is not None:
            query = test_identifier.copy()
            query['order'] = {'$gt': order}

        requests = [pymongo.DeleteMany(query)]

        for point in change_points:
            change_point = test_identifier.copy()
            change_point.update(point)
            index = thread_level_results['orders'].index(point['order'])
            change_point['task_id'] = thread_level_results['task_ids'][index]
            change_point['version_id'] = thread_level_results['version_ids'][index]
            requests.append(pymongo.InsertOne(change_point))

        if change_points:
            update = self._prepare_update_previous_change_point(test_identifier, change_points[0])
            if update:
                requests.append(update)

        try:
            with self.db.start_session() as session:
                with session.start_transaction():
                    bulk_write_result = self.db.change_points.bulk_write(requests)
                    LOG.debug(
                        "change points bulk_write",
                        test_identifier=test_identifier,
                        results=bulk_write_result.bulk_api_result)

            return thread_level_results['size'], len(change_points)
        except Exception as e:
            # pylint: disable=no-member
            LOG.warn(
                'compute_change_points failed',
                exc_info=True,
                details=e.details if hasattr(e, 'details') else str(e))
            raise

    def __getstate__(self):
        """
        Get state for pickle support.

        Multiprocessor pickles instances to serialize and deserialize to the sub-processes. But
        pickle cannot handle complex types (like a mongo client). However, these instances can
        be recreated on demand in the instance.

        :return: The pickle state.
        """
        return {
            'mongo_uri': self.mongo_uri,
            'min_points': self.min_points,
            'pvalue': self.pvalue,
            'mongo_repo': self.mongo_repo,
            'credentials': self.credentials
        }

    def __setstate__(self, state):
        """
        Set state for pickle support.

        :param dict state: The pickled state.
        """
        self.mongo_uri = state['mongo_uri']
        self._db = None
        self.min_points = state['min_points']
        self.pvalue = state['pvalue']
        self.mongo_repo = state['mongo_repo']
        self.credentials = state['credentials']
