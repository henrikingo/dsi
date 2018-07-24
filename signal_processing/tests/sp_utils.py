"""
Utils needed for tests in signal_processing/tests.
"""

import json


def load_json_file(filename):
    with open(filename, 'r') as json_file:
        return json.load(json_file)


def round_value(value, precision=1):
    """
    Round value if appropriate.

    :param float value: The value to round.
    :param int precision:  The precision to round to.
    :return: The rounded value.
    """
    if isinstance(value, float):
        return round(value, precision)
    elif isinstance(value, dict):
        return approx_dict(value, precision=precision)
    elif isinstance(value, list):
        return [round_value(element, precision=precision) for element in value]
    return value


def approx_dict(point, precision=1):
    """
    Convert all float values to floats of the requested precision.

    :param dict point: The point data.
    :param int precision: The required precision.
    :return: A new dict with floats to the required precision.
    """
    return {k: round_value(v, precision=precision) for k, v in point.items()}
