"""
Unit tests for `setup_baselines.py`.
"""

import unittest

import setup_baselines
from tests import test_utils


class TestSetupBaselines(unittest.TestCase):
    ''' Test suite for setup_baselines.py'''

    def setUp(self):
        '''
        Setup perfyaml for each test
        '''
        self.perfyaml = test_utils.read_fixture_yaml_file('perf.yml')

    def test_patchperfyamlstringssimple(self):
        '''
        Test patch_perf_yaml_strings with simple input
        '''

        input_object = {'functions': {'start server':
                                      [None,
                                       {'params': {'remote_file': 'original_mongod'}},
                                       {'params': {'remote_file': 'original_mongo'}}]},
                        'tasks': [{'depends_on': [{'name': 'foo'}, {'name': 'compile'}]}]}
        output_object = setup_baselines.patch_perf_yaml_strings(input_object, 'new_mongod',
                                                                'new_mongo')
        # Check that input is unchanged
        self.assertEqual(input_object['functions']['start server'][1]['params']['remote_file'],
                         'original_mongod')
        self.assertEqual(input_object['functions']['start server'][2]['params']['remote_file'],
                         'original_mongo')
        self.assertEqual(input_object['tasks'][0]['depends_on'][0]['name'], 'foo')
        self.assertEqual(input_object['tasks'][0]['depends_on'][1]['name'], 'compile')

        # Check otuptu is correct
        self.assertTrue('functions' in output_object)
        self.assertTrue('start server' in output_object['functions'])
        self.assertEqual(output_object['functions']['start server'][1]['params']['remote_file'],
                         'new_mongod')
        self.assertEqual(output_object['functions']['start server'][2]['params']['remote_file'],
                         'new_mongo')
        self.assertEqual(output_object['tasks'][0]['depends_on'][0]['name'], 'foo')
        # Length should be 1, because compile dependency was removed.
        self.assertEqual(len(output_object['tasks'][0]['depends_on']), 1)

    def test_patchstringwithfile(self):
        '''
        Test patch_perf_yam_strings with input from file
        '''

        # update version_link and shell_link
        output_object = setup_baselines.patch_perf_yaml_strings(self.perfyaml, 'new_mongod',
                                                                'new_mongo')
        reference_out = test_utils.read_fixture_yaml_file('perf.yml.simple.patch.ok')
        reference_in = test_utils.read_fixture_yaml_file('perf.yml')

        # Check that input is unchanged
        self.assertEqual(reference_in, self.perfyaml)

        # Check that return result is properly changed.
        self.assertEqual(reference_out, output_object)

    def test_patch_flags(self):
        '''
        Test patch_perf_yaml_mongod_flags
        '''

        updater = setup_baselines.BaselineUpdater()
        unchanged = updater.patch_perf_yaml_mongod_flags(self.perfyaml, '3.4.0')
        self.assertEqual(self.perfyaml, unchanged, 'No changes to mongod flags for 3.4.0')
        modified = updater.patch_perf_yaml_mongod_flags(self.perfyaml, '3.0.12')
        reference = test_utils.read_fixture_yaml_file('perf.yml.modified.mongodflags.ok')
        self.assertEqual(modified, reference, 'Remove inMemory and diagnostic parameters for 3.0')

    def test_patch_raise(self):
        '''
        Test that patch_perf_yaml raises if given version it doesn't know
        '''
        updater = setup_baselines.BaselineUpdater()
        with self.assertRaises(setup_baselines.UnsupportedBaselineError):
            updater.patch_perf_yaml(self.perfyaml, '1.6.0', 'performance')

    def test_patch_all(self):
        '''
        Test the patch_perf_yaml method on BaselineUpdater
        '''
        updater = setup_baselines.BaselineUpdater()

        modified = updater.patch_perf_yaml(self.perfyaml, '3.2.10', 'performance')
        reference = test_utils.read_fixture_yaml_file('perf.yml.master.3.2.10.ok')
        self.assertEqual(modified, reference, 'Patch for 3.2.10 on master')
        modified = updater.patch_perf_yaml(self.perfyaml, '3.0.14', 'performance')
        reference = test_utils.read_fixture_yaml_file('perf.yml.master.3.0.14.ok')
        modified = updater.patch_perf_yaml(self.perfyaml, '3.2.10', 'performance-3.2')
        reference = test_utils.read_fixture_yaml_file('perf.yml.perf-3.2.3.2.10.ok')
        self.assertEqual(modified, reference, 'Patch for 3.2.10 on perf-3.2')
        modified = updater.patch_perf_yaml(self.perfyaml, '3.0.14', 'performance-3.2')
        reference = test_utils.read_fixture_yaml_file('perf.yml.perf-3.2.3.0.14.ok')
        self.assertEqual(modified, reference, 'Patch for 3.0.14 on perf-3.2')

    def test_repeated_args(self):
        ''' Test format_repeated_args
        '''

        tasks = setup_baselines.format_repeated_args('-t', ['task1', 'task2', 'task3'])
        self.assertEqual(tasks, ['-t', 'task1', '-t', 'task2', '-t', 'task3'], 'format tasks')
        variants = setup_baselines.format_repeated_args('-v', ['variantA', 'variantB'])
        self.assertEqual(variants, ['-v', 'variantA', '-v', 'variantB'], 'format variants')

    def test_get_tasks(self):
        ''' Test get_tasks
        '''

        tasks = setup_baselines.get_tasks(self.perfyaml)
        reference = ['compile',
                     'query',
                     'views-query',
                     'views-aggregation',
                     'where',
                     'update',
                     'insert',
                     'geo',
                     'misc',
                     'singleThreaded',
                     'singleThreaded-wt-repl-comp',
                     'insert-wt-repl-comp',
                     'update-wt-repl-comp',
                     'misc-wt-repl-comp',
                     'singleThreaded-mmap-repl-comp',
                     'insert-mmap-repl-comp',
                     'update-mmap-repl-comp',
                     'misc-mmap-repl-comp',
                     'aggregation']
        self.assertEqual(tasks, reference)

    def test_get_variants(self):
        ''' Test get_variants
            '''

        variants = setup_baselines.get_variants(self.perfyaml)
        reference = ['linux-wt-standalone',
                     'linux-mmap-standalone',
                     'linux-wt-repl',
                     'linux-mmap-repl',
                     'linux-wt-repl-compare',
                     'linux-mmap-repl-compare']
        self.assertEqual(variants, reference)

    def test_prepare_patch(self):
        ''' Test prepare_patch

        '''

        cmd_args = setup_baselines.prepare_patch_cmd(self.perfyaml, '3.2.11', 'performance')
        reference = ['patch', '-p', 'performance', '-d', '3.2.11 baseline for project performance',
                     '-y', '-f', '-v', 'linux-wt-standalone', '-v', 'linux-mmap-standalone', '-v',
                     'linux-wt-repl', '-v', 'linux-mmap-repl', '-v', 'linux-wt-repl-compare', '-v',
                     'linux-mmap-repl-compare', '-t', 'query', '-t', 'views-query', '-t',
                     'views-aggregation', '-t', 'where', '-t', 'update', '-t',
                     'insert', '-t', 'geo', '-t', 'misc', '-t', 'singleThreaded', '-t',
                     'singleThreaded-wt-repl-comp', '-t', 'insert-wt-repl-comp', '-t',
                     'update-wt-repl-comp', '-t', 'misc-wt-repl-comp', '-t',
                     'singleThreaded-mmap-repl-comp', '-t', 'insert-mmap-repl-comp', '-t',
                     'update-mmap-repl-comp', '-t', 'misc-mmap-repl-comp', '-t', 'aggregation']
        # The first entry is the evergreen binary. Remove that.
        self.assertEqual(cmd_args[1:], reference, 'arguments to evergreen Popen call')

if __name__ == '__main__':
    unittest.main()