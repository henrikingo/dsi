"""
Read dsi config. (config.yml or dsi_config.yml)
"""

import os
import yaml


def find_config_file():
    # Highest priority first:
    search_paths = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yml"),
        os.path.expanduser("~/.dsi_config.yml")
    ]
    for path in search_paths:
        if os.path.exists(path):
            return path

    raise IOError("Did not find config.yml in repo root nor ~/.dsi_config.yml. "
                  "Please see /example_config.yml for a template.")


def read_config():
    with open(find_config_file()) as config_file:
        return yaml.load(config_file)
