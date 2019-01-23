"""
Outlier detection based on the GESD algorithm.
"""
from __future__ import print_function

from collections import namedtuple
from datetime import datetime
import sys

import jinja2
import numpy as np
import structlog
from scipy.stats import describe

from signal_processing.outliers.gesd import gesd

MAD_Z_SCORE = 'mad'
"""Use Median Abolute Deviation to calculate the z score."""

STANDARD_Z_SCORE = 'standard'
"""Use standard z score calculation."""

DEFAULT_MAX_OUTLIERS_PERCENTAGE = 0.20
""" The default max number of outliers to use in detection. 20% in this case. """

LOG = structlog.getLogger(__name__)

OutlierDetectionResult = namedtuple('OutlierDetectionResult', [
    'identifier', 'full_series', 'start', 'end', 'series', 'mad', 'significance_level',
    'num_outliers', 'gesd_result', 'adjusted_indexes'
])
"""
Represent the result of the outliers detection.

It contains the GESD algorithm result as well as some of the data and parameters used.
"""

HUMAN_READABLE_TEMPLATE_STR = '''
[ {{ now() }} ] Running: `{{ command_line }}`
## {{ identifier }}
## max_outliers={{ max_outliers }},
## start={{ start }},
## end={{ end }},
## p={{ p }}
## StartTime {{ full_series.create_times[start][:-4] }}
## EndTime {{ full_series.create_times[end][:-4] }}
## stats=(nobs={{ stats.nobs }},
##        minmax={{ stats.minmax }},
##        mean={{ stats.mean }},
##        std={{ std }},
##        variance={{ stats.variance }},
##        skewness={{ stats.skewness }},
##        kurtosis={{ stats.kurtosis }})

|  pos  | Index |   Z-Score  |  %change   | critical |   match  | accepted | revision |       Time       | {{ "%102s" | format(" ",) }} |
| ----- | ----- | ---------- | ---------- | -------- | -------- | -------- | -------- | ---------------- | {{ '-' * 102 }} |
{% for outlier in outliers -%}
| {{ "% -5s" | format(loop.index,) }} | {{ "% -5s" | format(outlier.index,) }} | {{ "% -9.3f" | format(outlier.z_score,) }} {{'M' if mad}} | {{ "% -9.3f" | format( 100 * ( full_series.series[outlier.index] - mean) / mean,) }}  | {{ "%-7.3f" | format(outlier.critical,) }}  |    {{ '(/)' if abs(outlier.z_score) > outlier.critical else '(x)' }}   |  {{ "%-5s" | format(loop.index <= count,) }}   | {{ full_series.revisions[outlier.index][0:8] }} | {{ full_series.create_times[outlier.index][:-4] }} | <{{outlier.version_id}}> |
{% endfor %}
'''

ENVIRONMENT = jinja2.Environment()
ENVIRONMENT.globals.update({
    'command_line': " ".join([arg if arg else "''" for arg in sys.argv]),
    'now': datetime.utcnow,
    'abs': abs,
})
HUMAN_READABLE_TEMPLATE = ENVIRONMENT.from_string(HUMAN_READABLE_TEMPLATE_STR)


def run_outlier_detection(full_series, start, end, series, test_identifier, outliers_percentage,
                          mad, significance_level):
    """
    Find the outliers for the given test.

    :param dict(list) full_series: The full time series data.
    :param int start: The start index within the full series.
    :param int end: The end index within the full series.
    :param list(float) series: The time series data.
    :param dict test_identifier: The test identifier.
    :param int outliers_percentage: The max outliers % value to use with GESD.
    :param bool mad: Whether the algorithm used the Median Absolute Deviation.
    :param float significance_level: The significance level used for the algorithm.
    """
    # pylint: disable=too-many-locals, too-many-arguments
    identifier = "{project} {variant} {task} {test} {thread_level}".format(**test_identifier)

    if len(series) == 1:
        return OutlierDetectionResult(identifier, full_series, start, end, series, mad,
                                      significance_level, 0, None, None)

    LOG.debug('investigating range', start=start, end=end, subseries=series)
    num_outliers = compute_max_outliers(outliers_percentage, test_identifier, series)

    gesd_result = gesd(series, num_outliers, significance_level=significance_level, mad=mad)

    LOG.debug("adjusting indexes", suspicious_indexes=gesd_result.suspicious_indexes, start=start)
    adjusted_indexes = np.array(gesd_result.suspicious_indexes, dtype=int) + start
    LOG.debug(
        "gesd outliers",
        series=full_series,
        start=start,
        count=gesd_result.count,
        suspicious_indexes=gesd_result.suspicious_indexes,
        test_statistics=gesd_result.test_statistics,
        critical_values=gesd_result.critical_values)

    return OutlierDetectionResult(identifier, full_series, start, end, series, mad,
                                  significance_level, num_outliers, gesd_result, adjusted_indexes)


def compute_max_outliers(outliers_percentage, test_identifier, series):
    """
    Compute outliers from percentage and series.

    :param float outliers_percentage: The percentage of outliers. The value must be greater than or
    equal to 0 and less than or equal to 1. 0 implies use the default value.
    :param dict test_identifier: The test identifier.
    :param list(float) series: The time series data.
    :return: The number of outliers.
    :rtype: int
    :see DEFAULT_MAX_OUTLIERS_PERCENTAGE
    :raises: AssertionError if outliers_percentage < 0 or outliers_percentage > 1.
    """
    assert 0 <= outliers_percentage <= 1.0, 'Outliers Percentage can only be between 0 and 100.'
    if outliers_percentage == 0:
        outliers_percentage = DEFAULT_MAX_OUTLIERS_PERCENTAGE

    if series is not None and np.size(series) > 0:
        num_outliers = int(len(series) * outliers_percentage)
        if num_outliers == 0:
            num_outliers = 1
        elif num_outliers >= len(series):
            num_outliers = len(series) - 1
    else:
        num_outliers = 0

    LOG.info(
        'compute_max_outliers',
        test_identifier=test_identifier,
        outliers_percentage=outliers_percentage,
        num_outliers=num_outliers,
        defaulted=outliers_percentage == 0,
        size_series=len(series))
    return num_outliers


def print_outliers(detection_result):
    """
    Print to stdout the results of the outliers detection algorithm.

    :param OutliersDetectionResult detection_result: The result of the outliers detection.
    :return: The lines that were printed to stdout.
    :rtype: list(str)
    """
    identifier = detection_result.identifier
    gesd_result = detection_result.gesd_result
    num_outliers = detection_result.num_outliers
    full_series = detection_result.full_series
    start = detection_result.start
    end = detection_result.end
    series = detection_result.series
    mad = detection_result.mad
    significance_level = detection_result.significance_level

    if detection_result.adjusted_indexes is not None:
        outliers = [
            _make_outlier_dict(mad, detection_result, i)
            for i in range(len(detection_result.adjusted_indexes))
        ]
    else:
        outliers = []

    dump = HUMAN_READABLE_TEMPLATE.stream(
        outliers=outliers,
        count=gesd_result.count if gesd_result else 0,
        max_outliers=num_outliers,
        full_series=full_series,
        start=start,
        end=end - 1,
        length=len(series),
        p=significance_level,
        identifier=identifier,
        mean=np.mean(series),
        std=np.std(series),
        stats=describe(series))

    lines = list(dump)
    for line in lines:
        print(line, end='')
    return lines


def _make_outlier_dict(mad, detection_result, outlier_index):
    outlier = detection_result.adjusted_indexes[outlier_index]

    gesd_result = detection_result.gesd_result
    value = gesd_result.test_statistics[outlier_index]
    critical_value = gesd_result.critical_values[outlier_index]
    version_id = detection_result.full_series['task_ids'][outlier]

    return dict(
        index=outlier,
        mad=mad,
        match=abs(value) > critical_value,
        accepted='   (/)' if outlier_index < gesd_result.count else '   (x)',
        z_score=round(value, 3),
        critical=round(critical_value, 3),
        version_id=version_id)
