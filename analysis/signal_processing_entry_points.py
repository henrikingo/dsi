""" Default values configured on signal_processing entry points"""
from signal_processing import detect_changes, detect_outliers, etl_jira_mongo, change_points_cli, \
    outliers_cli, etl_evg_mongo

from signal_processing.profiling import cli as profiling_cli

from bin.common.config import ConfigDict

CONFIG = ConfigDict('analysis').load()
TASK_ID = CONFIG['runtime']['task_id']
PATCH = CONFIG['runtime'].get('is_patch', False)
MONGO_URI = CONFIG['analysis']['mongo_uri']

DEFAULT_MAP = {'task_id': TASK_ID, 'is_patch': PATCH, 'mongo_uri': MONGO_URI}

DEFAULTS = dict(default_map=DEFAULT_MAP)

detect_changes.main.context_settings = DEFAULTS
detect_outliers.main.context_settings = DEFAULTS
etl_jira_mongo.main.context_settings = DEFAULTS
change_points_cli.cli.context_settings = DEFAULTS
outliers_cli.cli.context_settings = DEFAULTS
etl_evg_mongo.etl.context_settings = DEFAULTS
profiling_cli.context_settings = DEFAULTS

DETECT_CHANGES = detect_changes.main
DETECT_OUTLIERS = detect_outliers.main
ETL_JIRA_MONGO = etl_jira_mongo.main
CHANGE_POINTS = change_points_cli.cli
OUTLIERS = outliers_cli.cli
ETL_EVG_MONGO = etl_evg_mongo.etl
COMPARE_ALGORITHMS = profiling_cli
