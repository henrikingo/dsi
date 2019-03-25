"""
Run the outlier detection algorithm and display results.
"""
from __future__ import print_function
import json
import os
from collections import namedtuple
from datetime import datetime
import multiprocessing

import click
import pymongo
import structlog

import etl_helpers
import signal_processing.commands.helpers as helpers
import signal_processing.commands.jobs as jobs
import signal_processing.detect_changes as detect_changes
import signal_processing.outliers.detection as detection
from signal_processing.outliers.reject.task import TaskAutoRejector
from analysis.evergreen import evergreen_client
from bin.common import config, log

MINIMUM_POINTS = 15
"""
The minimum number of points required before an outlier can be automatically rejected. If there
are fewer performance points than 15, then skip rejections.
"""

MAX_CONSECUTIVE_REJECTIONS = 3
"""
The maximum number of fails allowed before a rejection is skipped. In this case, if the same
performance result is rejected 3 consecutive times then it is likely that the performance profile
has actually changed.
"""

SUSPICIOUS_TYPE = 'suspicious'
"""
The string value indicating that this point was deemed to be within the acceptable
performance range. The nature of the GESD algorithm means that in most cases points which are
not and cannot be outliers are marked as suspicious. Care should be taken in reading significance
into supicious points. You would really need to compare the z score and critical values and
take the position into account w.r.t the last detected outlier.
"""

DETECTED_TYPE = 'detected'
"""
The string value indicating that this point was deemed to be outside the acceptable
performance range.
"""

LOG = structlog.getLogger(__name__)


def print_result(job):
    """
    Print a description of the test and the results from running the E-Divisive algorithm on the
    points for that test.

    :param Job job: The job instance.
    """
    if job.exception is None:
        detection_result = job.result
        detection.print_outliers(detection_result)
    else:
        exception = job.exception
        descriptor = etl_helpers.create_descriptor(job.identifier).ljust(120)
        print("{0}: error: {1:1}".format(descriptor, str(exception)))


class DetectOutliersDriver(object):
    """
    An entry point for detecting outliers.
    """

    # pylint: disable=too-few-public-methods,too-many-arguments, too-many-instance-attributes
    def __init__(self,
                 perf_json,
                 mongo_uri,
                 outliers_percentage,
                 patch,
                 mad,
                 significance_level,
                 pool_size=None,
                 progressbar=False):
        """
        :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
        :param str mongo_uri: The uri to connect to the cluster.
        :param int outliers_percentage: The max outliers % input value for the GESD algorithm.
        :param bool patch: True if this is a patch.
        :param bool mad: Whether to use Median Absolute Deviation in the GESD algorithm.
        :param float significance_level: The significance level input value for the GESD algorithm.
        :param int pool_size: The size of the process pool size.
        :param bool progressbar: Whether to show a progress bar.
        """
        LOG.debug(
            "DetectOutliersDriver",
            perf_json=perf_json,
            mongo_uri=mongo_uri,
            outliers_percentage=outliers_percentage,
            patch=patch,
            mad=mad,
            significance_level=significance_level,
            pool_size=pool_size,
            progressbar=progressbar)
        self.perf_json = perf_json
        self.mongo_uri = mongo_uri

        self.outliers_percentage = outliers_percentage
        self.patch = patch
        self.mad = mad
        self.significance_level = significance_level

        if pool_size is None:
            pool_size = max(1, (multiprocessing.cpu_count() - 1) * 2)
        self.pool_size = pool_size
        self.progressbar = progressbar

    # pylint: disable=too-many-locals
    def run(self):
        """
        Run the analysis to compute any change points with the new data.
        :return: All the GESD outlier results.
        :rtype: list(Job).
        """
        model = detect_changes.PointsModel(self.mongo_uri)

        test_identifiers = helpers.extract_test_identifiers(self.perf_json)
        LOG.info('loaded tests', test_identifiers=len(test_identifiers))
        LOG.debug('loaded tests', test_identifiers=test_identifiers)
        label = 'detecting outliers'

        test_identifiers = [
            thread_identifier
            for test_identifier in test_identifiers for thread_identifier in
            helpers.generate_thread_levels(test_identifier, model.db.points)
        ]

        bar_template, show_item = helpers.query_terminal_for_bar()

        order = self.perf_json['order']

        job_list = [
            jobs.Job(
                _get_data_and_run_detection,
                arguments=(model, test_identifier, order, self.outliers_percentage, self.patch,
                           self.mad, self.significance_level),
                identifier=test_identifier) for test_identifier in test_identifiers
        ]
        start = datetime.now()
        completed_jobs = jobs.process_jobs(
            job_list, self.pool_size, label, self.progressbar, bar_template, show_item, key='test')

        for job in completed_jobs:
            print_result(job)

        duration = (datetime.now() - start).total_seconds()
        LOG.debug("Detect outliers complete", duration=duration, pool_size=self.pool_size)
        print("Detect outliers complete duration={} over {} processes.".format(
            duration, self.pool_size))

        return completed_jobs


def get_change_point_range(points_model, test_identifier, full_series, order):
    """Calculate the change point range for a given revision (order)."""
    change_points_col = points_model.db.get_collection(helpers.CHANGE_POINTS)
    change_points = list(
        change_points_col.find(test_identifier).sort([('order', pymongo.DESCENDING)]))

    if change_points:

        start_change_point = None
        start_change_point_index = None
        for i, change_point in enumerate(change_points):
            if change_point['order'] <= order:
                start_change_point = change_point
                start_change_point_index = i
                break

        if start_change_point is not None:
            start = full_series['orders'].index(start_change_point['order'])
            if start_change_point_index == 0:
                # The start change point is the last point.
                end = len(full_series['orders'])
            else:
                end_change_point = change_points[start_change_point_index - 1]
                end = full_series['orders'].index(end_change_point['order'])
        else:
            # order precedes all the change points, returning range before first change point.
            start = 0
            end = full_series['orders'].index(change_points[-1]['order'])

    else:
        start = 0
        end = len(full_series['orders'])

    series = full_series['series'][start:end]
    return start, end, series


# pylint: disable=too-many-arguments
def _get_data_and_run_detection(points_model, test_identifier, order, outliers_percentage, patch,
                                mad, significance_level):
    """
    Retrieve the time series data and run the outliers detection algorithm.
    """
    LOG.debug(
        "_get_data_and_run_detection",
        points_model=points_model,
        test_identifier=test_identifier,
        order=order,
        outliers_percentage=outliers_percentage,
        patch=patch,
        mad=mad,
        significance_level=significance_level)

    full_series = points_model.get_points(test_identifier, 0)
    start, end, series = get_change_point_range(points_model, test_identifier, full_series, order)

    outlier_results = detection.run_outlier_detection(full_series, start, end, series,
                                                      test_identifier, outliers_percentage, mad,
                                                      significance_level)

    _save_outliers(points_model, outlier_results, test_identifier)
    return outlier_results


Outlier = namedtuple('Outlier', [
    'type', 'project', 'variant', 'task', 'test', 'thread_level', 'revision', 'order', 'task_id',
    'version_id', 'create_time', 'change_point_revision', 'change_point_order', 'order_of_outlier',
    'z_score', 'critical_value', 'mad', 'significance_level', 'num_outliers'
])
"""
Tuple enacapsulating an outlier.

:ivar str type: The outlier type, 'detected' or 'suspicious'. Detected means that this outlier is
outside the acceptable range of performance. Suspicious means that this outlier is within the
acceptable range. The number of suspicious outliers is a factor of max outliers.
:ivar str project: The project name, e.g. 'sys-perf', 'performance'.
:ivar str variant: The variant, e.g. 'linux-standalone'.
:ivar str task: The task, e.g. 'change_streams_latency'.
:ivar str test: The test, e.g. 'canary_client-cpuloop-1x'.
:ivar str thread_level: The thread level, e.g. '1', 'max'.
:ivar str revision: The commit revision.
:ivar int order: The evergreen order value for this commit.
:ivar str create_time: The create time of the perf data.
:ivar str change_point_revision: The commit revision for the change point.
:ivar int change_point_order: The evergreen order value for the change point.
:ivar int order_of_outlier: The order that the outlier was checked by GESD. The lower the value,
the larger the scale of the outlier.
:ivar float z_score: The z score for this outlier with all previous outliers excluded.
:ivar float critical_value: The percent point function value,
:ivar bool mad: True if Median Absolute Value as used for z score calculation.
:ivar float significance_level: The significance level for the pvalue calculation.
:ivar int num_outliers: The max num outliers for the time series.
"""


def _translate_outliers(gesd_result, test_identifier, start, mad, significance_level, num_outliers,
                        full_series):
    # pylint: disable=too-many-locals
    """
    Translate raw GESD output to a list of Outlier instances.

    :param GesdResult gesd_result: The raw data gesd output.
    :param dict test_identifier: The dict that identifies this project / variant/ task / test /
    thread level result.
    :param int start: The start index in the full time series data.
    :param bool mad: Set to True if Median Absolute Deviation is being used.
    :param float significance_level: The significance level pvalue test.
    :param int num_outliers: The max number of outliers expected in the series.
    :param dict full_series: The time series data for the full task.
    :return: The GESD outlier results.
    :rtype: list[Outlier].
    """
    outliers = []
    if gesd_result is not None and gesd_result.count:
        count = gesd_result.count
        change_point_order = full_series['orders'][start]
        change_point_revision = full_series['revisions'][start]

        for pos, index in enumerate(gesd_result.suspicious_indexes):
            order = full_series['orders'][index + start]
            revision = full_series['revisions'][index + start]
            create_time = full_series['create_times'][index + start]
            task_id = full_series['task_ids'][index + start]
            version_id = full_series['version_ids'][index + start]
            critical_value = gesd_result.critical_values[pos]
            z_score = gesd_result.test_statistics[pos]
            outliers.append(
                Outlier(
                    type=DETECTED_TYPE if pos < count else SUSPICIOUS_TYPE,
                    project=test_identifier['project'],
                    variant=test_identifier['variant'],
                    task=test_identifier['task'],
                    test=test_identifier['test'],
                    thread_level=test_identifier['thread_level'],
                    revision=revision,
                    task_id=task_id,
                    version_id=version_id,
                    order=order,
                    create_time=create_time,
                    change_point_revision=change_point_revision,
                    change_point_order=change_point_order,
                    order_of_outlier=pos,
                    z_score=z_score,
                    critical_value=critical_value,
                    mad=mad,
                    significance_level=significance_level,
                    num_outliers=num_outliers))

    return outliers


def _save_outliers(points_model, outlier_results, test_identifier):
    # pylint: disable=too-many-locals
    """
    Store the outliers in a mongo collection.

    :param dict points_model: The model instance to access (read / write) to mongo.
    :param OutlierDetectionResult outlier_results: The GESD results.
    :param dict test_identifier: The dict that identifies this project / variant/ task / test /
    thread level result.

    :raises: mongoException on error. The write are applied in a transaction, changes are rolled
    back on error.
    """

    full_series = outlier_results.full_series
    gesd_result = outlier_results.gesd_result

    # start order is also the order of the associated change point
    start_order = full_series['orders'][outlier_results.start]
    end_order = full_series['orders'][outlier_results.end - 1]
    query = dict(**test_identifier)
    query['order'] = {'$gte': start_order}
    if end_order is not None:
        query['order']['$lt'] = end_order

    delete_old_outliers = query
    outliers = _translate_outliers(gesd_result, test_identifier, outlier_results.start,
                                   outlier_results.mad, outlier_results.significance_level,
                                   outlier_results.num_outliers, full_series)

    # Note: _asdict is not protected, the underscore is just to ensure there is no possibility of
    # a name clash.
    requests = [pymongo.DeleteMany(delete_old_outliers)] + \
               [pymongo.InsertOne(outlier._asdict()) for outlier in outliers]
    try:
        client = points_model.db.client
        outliers_collection = points_model.db['outliers']
        with client.start_session() as session:
            with session.start_transaction():
                bulk_write_result = outliers_collection.bulk_write(requests)

        LOG.debug(
            "outliers bulk_write",
            test_identifier=test_identifier,
            results=bulk_write_result.bulk_api_result)
    except Exception as e:
        # pylint: disable=no-member
        LOG.warn(
            'compute_change_points failed. Attempting to rollback.',
            exc_info=True,
            details=e.details if hasattr(e, 'details') else str(e))
        raise


def translate_field_name(field_name, max_thread_level):
    """
    Translate the field name based on whether it is in the results array or the main body of the
    document (for max thread level).

    :param str field_name: The field name (like rejected, etc.).
    :param bool max_thread_level: True if this is a max thread level field.
    :return: The translated field name, prepend 'results.$.' for max thread level.
    """
    if max_thread_level:
        return field_name
    return 'results.$.{}'.format(field_name)


def get_updates(auto_rejector):
    """
    Create the list of performance points updates to reflect the outlier and rejection status and
    the list of rejected tests.

    :param TaskAutoRejector auto_rejector: The auto rejector instance.
    :return: A list pymongo update operations.
    :see: module::signal_processing.reject.task.
    """
    updates = []
    if not auto_rejector.patch:
        order = auto_rejector.order

        for result in auto_rejector.results:
            full_series = result.full_series
            orders = full_series['orders']

            if orders:
                test_identifier = full_series['test_identifier']
                query = helpers.get_query_for_points(test_identifier)
                is_max = helpers.is_max_thread_level(test_identifier)

                outliers = list(result.outlier_orders)
                not_outliers = list(set(orders) - set(outliers))

                if not_outliers:
                    match = query.copy()
                    not_outliers_length = len(not_outliers)
                    if not_outliers_length == 1:
                        match['order'] = not_outliers[0]
                        update = pymongo.UpdateOne(match, {
                            '$set': {
                                translate_field_name('outlier', is_max): False
                            }
                        })
                    else:
                        match['order'] = {'$in': not_outliers}
                        update = pymongo.UpdateMany(match, {
                            '$set': {
                                translate_field_name('outlier', is_max): False
                            }
                        })
                    updates.append(update)

                rejected = order in outliers and result.latest
                if rejected:
                    outliers.remove(order)
                if outliers:
                    match = query.copy()
                    if len(outliers) == 1:
                        match['order'] = outliers[0]
                        update = pymongo.UpdateOne(match, {
                            '$set': {
                                translate_field_name('outlier', is_max): True
                            }
                        })
                    else:
                        match['order'] = {'$in': outliers}
                        update = pymongo.UpdateMany(match, {
                            '$set': {
                                translate_field_name('outlier', is_max): True
                            }
                        })
                    updates.append(update)

                if rejected:
                    match = query.copy()
                    match['order'] = order
                    update = pymongo.UpdateOne(
                        match, {
                            '$set': {
                                translate_field_name('outlier', is_max): True,
                                translate_field_name('rejected', is_max): True,
                            }
                        })
                    updates.append(update)

    return updates


def update_outlier_status(model, updates):
    # pylint: disable=no-member
    """
    Update performance points to include outlier and rejection status.

    :param PointModel model: The point model instance.
    :param list() updates: The list of pymongo point updates for this set of results.
    """
    if updates:
        try:
            client = model.db.client
            points_collection = model.db.points
            with client.start_session() as session:
                with session.start_transaction():
                    bulk_write_result = points_collection.bulk_write(updates)

            LOG.debug(
                "outliers bulk_write", updates=updates, results=bulk_write_result.bulk_api_result)
        except Exception as e:
            # pylint: disable=no-member
            LOG.warn(
                'compute_change_points failed. Attempting to rollback.',
                exc_info=True,
                details=e.details if hasattr(e, 'details') else str(e))
            raise


def write_rejects(rejects, rejects_file):
    """
    Write reject data to filename. If rejects is an empty list or None and filename exists, it
    will be deleted. If rejects is not empty then the test identifiers for each result are written
    to the file.

    :param list(TestAutoReject) rejects: The list of rejected results,
    :param str rejects_file: The filename to write.
    """
    if os.path.exists(rejects_file):
        os.remove(rejects_file)
    if rejects:
        with open(rejects_file, 'w+') as out:
            output = json.dumps(
                {
                    'rejects': [reject.test_identifier for reject in rejects]
                },
                out,
                indent=2,
                separators=[',', ': '],
                sort_keys=True)
            print('write_rejects ' + output)
            out.write(output)


def load_status_report(filename='report.json'):
    """
    Load the report status from the json file. If an error occurs then the function returns None,
    and the rejector should attempt to handle this as gracefully as possible. However it is very
    unlikely that we get to this code in this case.

    :param str filename: The report filename.
    :return: The test status report. On an exception, this function returns None.
    :rtype: dict or None
    """
    try:
        with open(filename) as file_handle:
            report = json.load(file_handle)
        return report
    # pylint: disable=bare-except
    except:
        LOG.warn('load_status_report failed', exc_info=True)
        return None


def detect_outliers(task_id,
                    mongo_uri,
                    outliers_percentage,
                    patch,
                    mad,
                    significance_level,
                    pool_size,
                    rejects_file,
                    max_consecutive_rejections,
                    minimum_points,
                    progressbar=False):
    # pylint: disable=too-many-locals
    """
    Setup and run the detect outliers algorithm.
    """
    evg_client = evergreen_client.Client()
    perf_json = evg_client.query_perf_results(task_id)
    test_identifiers = helpers.extract_test_identifiers(perf_json)
    if test_identifiers:
        status = load_status_report()

        project = test_identifiers[0]['project']
        variant = test_identifiers[0]['variant']
        task = test_identifiers[0]['task']

        outliers_driver = DetectOutliersDriver(
            perf_json,
            mongo_uri,
            outliers_percentage,
            patch,
            mad,
            significance_level,
            pool_size=pool_size,
            progressbar=progressbar)
        completed_jobs = outliers_driver.run()

        successful_jobs = [job.result for job in completed_jobs if not job.exception]
        if successful_jobs:
            auto_rejector = TaskAutoRejector(successful_jobs, project, variant, task,
                                             perf_json['order'], mongo_uri, patch, status,
                                             max_consecutive_rejections, minimum_points)

            updates = get_updates(auto_rejector)
            update_outlier_status(auto_rejector.model, updates)

            rejects = auto_rejector.filtered_rejects()
        else:
            rejects = []

        LOG.info('detect_outliers', rejects=rejects)
        write_rejects(rejects, rejects_file)
    else:
        LOG.info('detect_outliers: no tests')
        completed_jobs = []
    return completed_jobs


@click.command()
@click.pass_context
@click.option(
    '--max-outliers',
    type=float,
    default=0.0,
    callback=helpers.validate_outlier_percentage,
    help="""The max number of outliers as a percentage of the series length.
0 means use the default. Valid values are 0.0 to 1.0. """)
@click.option(
    '--mad/--no-mad', 'mad', is_flag=True, default=False, help='Use Median Absolute Deviation')
@click.option(
    '--significance',
    '-p',
    'significance_level',
    type=float,
    default=0.05,
    help='Significance level')
@click.option('-l', '--logfile', default='detect_outliers.log', help='The log file location.')
@click.option(
    '--pool-size', default=None, help='The multiprocessor pool size. None => num(cpus) -1.')
@click.option('--rejects-file', default='rejects.json', help='The rejects file location.')
@click.option('-v', 'verbose', count=True, help='Control the verbosity.')
@click.option(
    '--rejections',
    'max_consecutive_rejections',
    default=MAX_CONSECUTIVE_REJECTIONS,
    help='The max number of consecutive rejections (' + str(MAX_CONSECUTIVE_REJECTIONS) +
    '). When there are more than this number of rejections then any rejects are skipped.')
@click.option(
    '--minimum',
    'minimum_points',
    default=MINIMUM_POINTS,
    help='The minimum number of points required in a stationary range (' + str(MINIMUM_POINTS) +
    '). Rejections are disabled until this number of points are available.')
@click.option('--progressbar/--no-progressbar', default=False)
def main(context, max_outliers, mad, significance_level, logfile, pool_size, verbose, rejects_file,
         max_consecutive_rejections, minimum_points, progressbar):
    """
    Main function.
    """
    # pylint: disable=too-many-locals
    rejects_file = os.path.expanduser(rejects_file)
    log.setup_logging(True if verbose > 0 else False, filename=logfile)
    conf = config.ConfigDict('analysis')
    conf.load()

    task_id = conf['runtime']['task_id']
    mongo_uri = conf['analysis']['mongo_uri']
    patch = conf['runtime'].get('is_patch', False)

    if pool_size is not None:
        pool_size = int(pool_size)

    job_list = detect_outliers(
        task_id,
        mongo_uri,
        max_outliers,
        patch,
        mad,
        significance_level,
        pool_size,
        rejects_file,
        max_consecutive_rejections,
        minimum_points,
        progressbar=progressbar)

    jobs_with_exceptions = [job for job in job_list if job.exception is not None]
    jobs.handle_exceptions(context, jobs_with_exceptions, logfile)
