#!/usr/bin/env python2.7
"""Test that json files are sorted and indented in the way we require."""
import glob
import json
import os
import unittest

class TestJsonFiles(unittest.TestCase):
    """Read json files as string. Parse and dump as string again, expect result to be identical."""

    def test_json_files(self):
        """Validate sorting and indentation on json files."""
        files = glob.glob('analysis/*/*.json')

        for file_name in files:
            if os.path.isfile(file_name):
                print file_name
                with open(file_name) as file_handle:
                    json_as_str = "".join(file_handle.readlines())
                with open(file_name) as file_handle:
                    json_as_dict = json.load(file_handle)
                    correct_json = json.dumps(json_as_dict, indent=4,
                                              separators=[',', ':'], sort_keys=True)
                self.assertEquals(json_as_str, correct_json)

if __name__ == '__main__':
    unittest.main()
