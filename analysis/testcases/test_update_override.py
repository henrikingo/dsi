# Copyright 2015 MongoDB Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit test for the UpdateOverride class. nosetests: run from dsi or dsi/analysis."""

import filecmp
import logging
import os
import unittest

from evergreen.update_override import UpdateOverride  # pylint: disable=import-error


class TestUpdateOverride(unittest.TestCase):
    """Evaluates how the Override JSON output changes after a call to update_override
    in the UpdateOverride class
    """

    def setUp(self):
        """Specifies the paths to output JSON, warning, and log files"""
        self.abs_path = os.path.dirname(os.path.abspath(__file__))
        self.file_path_prefix = os.path.join(self.abs_path, 'unittest-files')
        self.output_file = os.path.join(self.file_path_prefix,
                                        'update_override_test_output.json')
        self.warn_out = os.path.join(self.file_path_prefix, 'update_override_test.err')
        self.log_out = os.path.join(self.file_path_prefix, 'update_override_test.out')

    def test_update_override(self):  # pylint: disable=too-many-locals
        """Comparison of UpdateOverride.update_override output with the expected results
        obtained from the original update override script.
        """
        project = 'performance'
        git_hash = 'c2af7ab'
        variants = '.*'
        task = 'query'
        tests_to_update = 'Queries.FindProjectionDottedField$|Queries.FindProjectionThreeFields$'
        override_file = os.path.join(self.abs_path, 'perf_override.json')
        config_file = os.path.join(self.abs_path, 'config.yml')

        ticket = 'PERF-REF'
        verbose = True

        warner = logging.getLogger('override.update.warnings')
        logger = logging.getLogger('override.update.information')

        warn_fh = logging.FileHandler(self.warn_out)
        warn_fh.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        warner.addHandler(warn_fh)

        log_fh = logging.FileHandler(self.log_out)
        logger.addHandler(log_fh)

        update_obj = UpdateOverride(project,
                                    git_hash,
                                    variants.split('|'),
                                    task.split('|'),
                                    tests_to_update.split('|'),
                                    override_file,
                                    config_file=config_file,
                                    ticket=ticket,
                                    verbose=verbose)
        update_obj.update_override()
        update_obj.ovr.save_to_file(self.output_file)

        expected_json = os.path.join(self.file_path_prefix, 'update_override_exp.json.ok')
        expected_warnings = os.path.join(self.file_path_prefix, 'update_override_exp.err.ok')
        expected_debug = os.path.join(self.file_path_prefix, 'update_override_exp.out.ok')

        self.assertTrue(filecmp.cmp(self.output_file, expected_json))
        self.assertTrue(filecmp.cmp(self.warn_out, expected_warnings))
        self.assertTrue(filecmp.cmp(self.log_out, expected_debug))

    def tearDown(self):
        """Deletes output JSON, warning, and log files from test case"""
        os.remove(self.output_file)
        os.remove(self.warn_out)
        os.remove(self.log_out)

if __name__ == '__main__':
    unittest.main()
