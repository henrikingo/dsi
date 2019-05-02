"""
Unit tests helpers for signal_processing/outliers/task.py.
"""
import os

from mock import MagicMock

from signal_processing.model.configuration import OutlierConfiguration, DEFAULT_CONFIG
from signal_processing.outliers.reject.task import TestAutoRejector, TaskAutoRejector
from test_lib.fixture_files import FixtureFiles

FIXTURE_FILES = FixtureFiles(os.path.dirname(__file__))


def test_identifier(test='test_name', thread_level='1'):
    return {'test': test, 'thread_level': thread_level}


def create_test_rejector(test='test_name',
                         thread_level='1',
                         task=None,
                         size=15,
                         rejected=[],
                         max_consecutive_rejections=3,
                         minimum_points=15,
                         gesd_result=None,
                         orders=None,
                         adjusted_indexes=None,
                         last_order=None):
    full_series = dict(
        test_identifier=test_identifier(test, thread_level),
        size=size,
        rejected=rejected,
        orders=orders)
    mock_result = MagicMock(
        name='result',
        full_series=full_series,
        gesd_result=gesd_result,
        adjusted_indexes=adjusted_indexes)
    if task is None:
        task = MagicMock(name='task', order=last_order)
    override_config = OutlierConfiguration(
        max_outliers=DEFAULT_CONFIG.max_outliers,
        mad=DEFAULT_CONFIG.mad,
        significance_level=DEFAULT_CONFIG.significance_level,
        max_consecutive_rejections=max_consecutive_rejections,
        minimum_points=minimum_points,
        canary_pattern=DEFAULT_CONFIG.canary_pattern,
        correctness_pattern=DEFAULT_CONFIG.correctness_pattern)
    rejector = TestAutoRejector(mock_result, task, override_config)
    rejector._config = override_config
    return rejector, mock_result, task


def create_task_rejector(results=[],
                         project='project',
                         variant='variant',
                         task='task',
                         order=0,
                         revision='revision',
                         mongo_uri='mongo_uri',
                         patch=False,
                         status=None,
                         config=None):
    if not status:
        status = {'failures': 0}
    perf_json = {'order': order, 'revision': revision}
    tar = TaskAutoRejector(results, project, variant, task, perf_json, mongo_uri, patch, status,
                           config)
    config = DEFAULT_CONFIG if config is None else config
    tar._config = config
    for result in tar.results:
        result._config = config
    return tar


def load_status(filename):
    """
    Load the report.json content from the 'status' field.
    The 'task_id' field allows you to track back to the dsi data.
    Although note: some of these files were edited.
    :param str filename: The json file with the report.json status data.
    :return: A dict of the report.json status data.
    """
    status = FIXTURE_FILES.load_json_file(filename)
    return status['status']
