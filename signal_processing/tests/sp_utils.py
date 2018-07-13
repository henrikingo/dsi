"""
Utils needed for tests in signal_processing/tests.
"""

import json


def load_json_file(filename):
    with open(filename, 'r') as json_file:
        return json.load(json_file)
