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
import signal_processing.outliers.detection as detection
from signal_processing.model.configuration import ConfigurationModel, \
    combine_outlier_configs, OutlierConfiguration
from signal_processing.model.points import PointsModel
from signal_processing.outliers.reject.task import TaskAutoRejector
from analysis.evergreen import evergreen_client
from bin.common import config, log

DETECTED_LOW_CONFIDENCE = 'detected-low-confidence'
"""
The string value indicating that this point was deemed to be within the acceptable
performance range. The nature of the GESD algorithm means that in most cases points which are
not and cannot be outliers are marked as suspicious / low confidence. Care should be taken in
reading significance into suspicious points. You would really need to compare the z score and
critical values and take the position into account w.r.t the last detected outlier.
"""

DETECTED_HIGH_CONFIDENCE = 'detected-high-confidence'
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
                 override_config,
                 mongo_uri,
                 patch,
                 pool_size=None,
                 progressbar=False):
        """
        :param dict perf_json: The raw data json file from Evergreen mapped to a Python dictionary.
        :param dict override_config: A dict containing the override configuration values. These
        values will override the values from the configuration collection. The pertinent values are
        outliers_percentage (float between 0 and 1), mad (bool), significance_level (float between
        0 and 1). A missing key implies no override, use the value from the collection.
        :param str mongo_uri: The uri to connect to the cluster.
        :param bool patch: True if this is a patch.
        :param int pool_size: The size of the process pool size.
        :param bool progressbar: Whether to show a progress bar.
        """
        LOG.debug(
            "DetectOutliersDriver",
            perf_json=perf_json,
            mongo_uri=mongo_uri,
            override_config=override_config,
            patch=patch,
            pool_size=pool_size,
            progressbar=progressbar)
        self.perf_json = perf_json
        self.override_config = override_config
        self.mongo_uri = mongo_uri

        self.patch = patch

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
        points_model = PointsModel(self.mongo_uri)
        configuration_model = ConfigurationModel(self.mongo_uri)

        test_identifiers = helpers.extract_test_identifiers(self.perf_json)
        LOG.info('loaded tests', test_identifiers=len(test_identifiers))
        LOG.debug('loaded tests', test_identifiers=test_identifiers)
        label = 'detecting outliers'

        test_identifiers = [
            thread_identifier
            for test_identifier in test_identifiers for thread_identifier in
            helpers.generate_thread_levels(test_identifier, points_model.db.points)
        ]

        bar_template, show_item = helpers.query_terminal_for_bar()

        order = self.perf_json['order']

        job_list = [
            jobs.Job(
                _get_data_and_run_detection,
                arguments=(points_model, configuration_model, test_identifier, order,
                           self.override_config, self.patch),
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
    """
    Calculate the change point range for a given revision (order).

    The cases to handle are:
      1. no change points, so start = 0 and end = None.
      1. one change point and order is before, so start = 0 and end = change point.
      1. one change point and order is after, so start = change point and end = None.
      1. multiple change points and order is between 2, so start = previous change point and
      end = next change point.

    start is always inclusive and end is always exclusive.

    :param PointsModel points_model: The points model instance.
    :param dict test_identifier: The dict to use to query for data.
    :param dict full_series: The full data (series, orders, revisions etc) for the test.
    :param int order: The order value for this revision.

    :return: A tuple containing
                *start*: the index within the full series.
                *end*: the index within the full series. None is returned to indicate the remainder
                of the list.
                *series*: the data between start (inclusive) and end(exclusive).
    :rtype: tuple(int, int, list).
    """
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
                end = None
            else:
                end_change_point = change_points[start_change_point_index - 1]
                end = full_series['orders'].index(end_change_point['order'])
        else:
            # order precedes all the change points, returning range before first change point.
            start = 0
            end = full_series['orders'].index(change_points[-1]['order'])
    else:
        start = 0
        end = None

    if end is None:
        series = full_series['series'][start:]
    else:
        series = full_series['series'][start:end]

    return start, end, series


# pylint: disable=too-many-arguments
def _get_data_and_run_detection(points_model, configuration_model, test_identifier, order,
                                override_config, patch):
    """
    Retrieve the time series data and run the outliers detection algorithm.
    """
    LOG.debug(
        "_get_data_and_run_detection",
        points_model=points_model,
        configuration_model=configuration_model,
        test_identifier=test_identifier,
        order=order,
        override_config=override_config,
        patch=patch)

    configuration = combine_outlier_configs(test_identifier,
                                            configuration_model.get_configuration(test_identifier),
                                            override_config)

    full_series = points_model.get_points(test_identifier, 0)
    start, end, series = get_change_point_range(points_model, test_identifier, full_series, order)

    outlier_results = detection.run_outlier_detection(
        full_series, start, end, series, test_identifier, configuration.max_outliers,
        configuration.mad, configuration.significance_level)

    _save_outliers(points_model, outlier_results, test_identifier, configuration)
    return outlier_results


Outlier = namedtuple('Outlier', [
    'type', 'project', 'variant', 'task', 'test', 'thread_level', 'revision', 'order', 'task_id',
    'version_id', 'create_time', 'change_point_revision', 'change_point_order', 'order_of_outlier',
    'z_score', 'critical_value', 'num_outliers', 'configuration'
])
"""
Tuple encapsulating an outlier.

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
:ivar int num_outliers: The max num outliers for the time series.
:ivar dict configuration: The configuration params used to calculate the outliers.
"""


def _translate_outliers(gesd_result, test_identifier, start, num_outliers, full_series,
                        configuration):
    # pylint: disable=too-many-locals
    """
    Translate raw GESD output to a list of Outlier instances.

    :param GesdResult gesd_result: The raw data gesd output.
    :param dict test_identifier: The dict that identifies this project / variant / task / test /
    thread level result.
    :param int start: The start index in the full time series data.
    :param int num_outliers: The max number of outliers expected in the series.
    :param dict full_series: The time series data for the full task.
    :return: The GESD outlier results.
    :rtype: list[Outlier].
    """
    outliers = []
    if gesd_result is not None and gesd_result.suspicious_indexes:
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
                    type=DETECTED_HIGH_CONFIDENCE if pos < count else DETECTED_LOW_CONFIDENCE,
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
                    num_outliers=num_outliers,
                    configuration=configuration._asdict()))

    return outliers


def _save_outliers(points_model, outlier_results, test_identifier, configuration):
    # pylint: disable=too-many-locals
    """
    Store the outliers in a mongo collection.

    :param dict points_model: The model instance to access (read / write) to mongo.
    :param OutlierDetectionResult outlier_results: The GESD results.
    :param dict test_identifier: The dict that identifies this project / variant/ task / test /
    thread level result.
    :param OutliersConfiguration configuration: The configuration tuple.

    :raises: mongoException on error. The write are applied in a transaction, changes are rolled
    back on error.
    """

    full_series = outlier_results.full_series
    gesd_result = outlier_results.gesd_result

    orders = full_series['orders']
    start_order = orders[outlier_results.start]
    query = dict(**test_identifier)
    query['order'] = {'$gte': start_order}
    if outlier_results.end is not None:
        query['order']['$lt'] = orders[outlier_results.end]

    delete_old_outliers = query
    outliers = _translate_outliers(gesd_result, test_identifier, outlier_results.start,
                                   outlier_results.num_outliers, full_series, configuration)

    # Note: _asdict is not protected, the underscore is just to ensure there is no possibility of
    # a name clash.
    requests = [pymongo.DeleteMany(delete_old_outliers)] + \
               [pymongo.InsertOne(outlier._asdict()) for outlier in outliers]
    try:
        client = points_model.db.client
        outliers_collection = points_model.db['outliers']
        with client.start_session() as session:
            with session.start_transaction():
                bulk_write_result = outliers_collection.bulk_write(requests, ordered=True)

        LOG.debug(
            "outliers bulk_write",
            test_identifier=test_identifier,
            results=bulk_write_result.bulk_api_result)
    except:  # pylint: disable=bare-except
        LOG.warn('detect_outliers failed.', exc_info=1)
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

                rejected = result.reject(order)
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
                'detect outliers failed - rollback.',
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
                    override_config,
                    mongo_uri,
                    patch,
                    pool_size,
                    rejects_file,
                    progressbar=False):
    # pylint: disable=too-many-locals
    """
    Setup and run the detect outliers algorithm.

    :param str task_id: The task identifier from evergreen.
    :param dict() override_config:  The override configuration supplied by the end user.
    :param str mongo_uri: The mongodb locator.
    :param bool patch: True iff this is a patch result.
    :param int pool_size: The pool size. 0 implies no multiprocessing.
    :param str rejects_file: The name of the rejects file.
    :param bool progressbar: True if we should render / use a progress bar.
    :return: A list of the completed jobs.
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
            override_config,
            mongo_uri,
            patch,
            pool_size=pool_size,
            progressbar=progressbar)
        completed_jobs = outliers_driver.run()

        successful_jobs = [job.result for job in completed_jobs if not job.exception]
        if successful_jobs:
            auto_rejector = TaskAutoRejector(
                successful_jobs,
                project,
                variant,
                task,
                perf_json,
                mongo_uri,
                patch,
                status,
                override_config,
            )

            updates = get_updates(auto_rejector)
            update_outlier_status(auto_rejector.points_model, updates)

            rejects = auto_rejector.filtered_rejects()
            if auto_rejector.whitelisted:
                LOG.info(
                    'detect_outliers task whitelisted',
                    rejects=rejects,
                    whitelisted=auto_rejector.whitelisted)
                rejects = []
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
    '-l',
    '--logfile',
    default='detect_outliers.log',
    help='The log file location. Defaults to ./detect_outliers.log.')
@click.option(
    '--pool-size',
    type=int,
    default=None,
    help='The multiprocessor pool size. None => num(cpus) -1. 0 means run without multiprocessing.')
@click.option(
    '--rejects-file',
    default='rejects.json',
    help='The rejects file location. Rejected test results will be written to this file.')
@click.option(
    '--progressbar/--no-progressbar',
    default=False,
    help='Determines if a process bar should be rendered.')
@click.option('-v', 'verbose', count=True, help='Control the verbosity.')
@click.option(
    '--max-outliers',
    callback=helpers.validate_outlier_percentage,
    type=float,
    default=None,
    help="""The max number of outliers as a percentage of the series length.
0 means use the default. Valid values are 0.0 to 1.0.""")
@click.option(
    '--mad/--no-mad', 'mad', is_flag=True, default=None, help='Use Median Absolute Deviation')
@click.option(
    '--significance',
    '-p',
    'significance_level',
    callback=helpers.validate_outlier_percentage,
    type=float,
    default=None,
    help='Significance level')
@click.option(
    '--rejections',
    'max_consecutive_rejections',
    type=int,
    default=None,
    help='The max number of consecutive rejections.' +
    'When there are more than this number of rejections then any rejects are skipped.')
@click.option(
    '--minimum',
    'minimum_points',
    default=None,
    type=int,
    help='The minimum number of points required in a stationary range.' +
    ' Rejections are disabled until this number of points are available.')
def main(context, logfile, pool_size, verbose, rejects_file, progressbar, max_outliers, mad,
         significance_level, max_consecutive_rejections, minimum_points):
    # pylint: disable=anomalous-backslash-in-string
    """
Detect outliers using the GESD algorithm.

It is expected that this command is invoked in the top level directory of an evergreen project and
that no parameters are required (i.e it is provided 'batteries included' with sensible defaults).

It is also possible to download a DSI archive from an evergreen task, extract the contents and run
the command in the root if this archive.

Note: care should be taken in this case to ensure that you use a local mongo instance
by editing the analysis.yml file.

E.g:

\b
   $> sed -i.bak "s/^mongo_uri:.*$/mongo_uri: 'mongodb:\/\/localhost\/perf'/"  analysis.yml

\b
The following configuration options are also stored in the configuration collection:
    --max-outliers: used by GESD
    --mad/--no-mad: used by GESD
    --significance: used by GESD
    --rejections: used to control rejection of results
    --minimum: used to control rejection of results

The defaults value for any of these options is None. Semantically None means use the configuration
collection.

However when a command option is provided it overrides the configuration collection values. See the
output of the configure command:

   $> outliers configure --help

Invocation

   $> detect-outliers


"""
    # pylint: disable=too-many-locals

    # A value of None means use the default. A non-None value will override the value from the
    # configuration collection.
    override_config = OutlierConfiguration(
        max_outliers=max_outliers,
        mad=mad,
        significance_level=significance_level,
        max_consecutive_rejections=max_consecutive_rejections,
        minimum_points=minimum_points)

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
        override_config,
        mongo_uri,
        patch,
        pool_size,
        rejects_file,
        progressbar=progressbar)

    jobs_with_exceptions = [job for job in job_list if job.exception is not None]
    jobs.handle_exceptions(context, jobs_with_exceptions, logfile)
