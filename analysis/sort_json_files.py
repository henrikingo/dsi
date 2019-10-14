#!/usr/bin/env python2.7
"""Helper script to rewrite override json files in a properly sorted and indented structure."""
import glob
import json
import os


def rewrite_all():
    """Read all json files, parse, sort, and write back again."""
    files = glob.glob('analysis/*/*.json')

    for file_name in files:
        if os.path.isfile(file_name):
            print file_name
            with open(file_name) as file_handle:
                json_as_dict = json.load(file_handle)
                correct_json = json.dumps(json_as_dict,
                                          indent=4,
                                          separators=[',', ':'],
                                          sort_keys=True)

            with open(file_name, "w") as out_file:
                out_file.write(correct_json)


if __name__ == '__main__':
    rewrite_all()
