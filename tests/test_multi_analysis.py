"""Unit tests for util/multi_analysis.py"""

import unittest

from tests import test_utils
from multi_analysis import MultiEvergreenAnalysis, main


class TestMultiEvergreenAnalysis(unittest.TestCase):
    """
    Test the MultiEvergreen client class.
    """
    def test_parse_options(self):
        """MultiEvergreenAnalysis: parse options."""
        expected = {
            'evergreen_config': test_utils.repo_root_file_path('config.yml'),
            'csv': True,
            'json': False,
            'yml': False,
            'id': ['587773af3ff120ab9000946', '587773b03ff1220ab900094a']
        }
        args = ['587773af3ff120ab9000946', '587773b03ff1220ab900094a',
                '--evergreen-config', test_utils.repo_root_file_path('config.yml')]
        client = MultiEvergreenAnalysis(args)
        client.parse_options()
        self.assertEqual(client.config, expected)

    def test_parse_options2(self):
        """MultiEvergreenAnalysis: parse more advanced options."""
        input_file = test_utils.fixture_file_path('multi_patch_builds.yml')
        expected_config = {
            'evergreen_config': test_utils.repo_root_file_path('config.yml'),
            'csv': False,
            'json': True,
            'yml': False,
            'out': 'outfile.json',
            'id': [],
            'continue': input_file
        }
        args = ['--json', '--out', 'outfile.json',
                '--continue', input_file,
                '--evergreen-config', test_utils.repo_root_file_path('config.yml')]
        client = MultiEvergreenAnalysis(args)
        client.parse_options()
        self.assertEqual(client.config, expected_config)
        self.assertEqual(client.builds[1]['ID'], '5873a2623ff1224e8e0003ee')

    def test_aggregate_results(self):
        """MultiEvergreenAnalysis.aggregate_results()"""
        data = [{'a_variant':
                     {'a_task':
                          {'data':
                               {'results': [{'name': 'a_test',
                                             'results': {'32': {'ops_per_sec': 111.123,
                                                                'ops_per_sec_values': [111.123,
                                                                                       123.111,
                                                                                       234.123]},
                                                         '64': {'ops_per_sec': 222.234,
                                                                'ops_per_sec_values': [222.234,
                                                                                       333.123,
                                                                                       444.111]}
                                                        }
                                            }]
                               }
                          }
                     }
                },
                {'a_variant':
                     {'a_task':
                          {'data':
                               {'results': [{'name': 'a_test',
                                             'results': {'32': {'ops_per_sec': 123,
                                                                'ops_per_sec_values': [123.123,
                                                                                       234.234,
                                                                                       345.345]},
                                                         '64': {'ops_per_sec': 234,
                                                                'ops_per_sec_values': [234.234,
                                                                                       345.345,
                                                                                       456.456]}
                                                        }
                                            }]
                               }
                          }
                     }
                }]
        expected = {'a_variant':
                        {'a_task':
                             {'a_test':
                                  {32:
                                       {'all_variance_to_mean': 44.10677573939485,
                                        'it_range_to_median': [0.999098374637522,
                                                               0.9487179487179488],
                                        'it_max': [234.123,
                                                   345.345],
                                        'it_variance': [4599.396047999999,
                                                        12345.654321000002],
                                        'it_range': [122.99999999999999,
                                                     222.22200000000004],
                                        'all_min': 111.123,
                                        'all_median': 178.623,
                                        'it_median': [123.111,
                                                      234.234],
                                        'min': 111.123,
                                        'all_variance': 8608.6061151,
                                        'all_range_to_median': 1.3112645068104334,
                                        'max': 123,
                                        'all_range': 234.22200000000004,
                                        'variance': 70.53156449999994,
                                        'variance_to_mean': 0.6025171768685686,
                                        'it_min': [111.123,
                                                   123.123],
                                        'all_max': 345.345,
                                        'it_variance_to_mean': [29.46083467098815,
                                                                52.706500000000005],
                                        'average': 117.0615,
                                        'median': 117.0615,
                                        'ops_per_sec': [111.123, 123],
                                        'ops_per_sec_values': [[111.123, 123.111, 234.123],
                                                               [123.123, 234.234, 345.345]],
                                        'range': 11.876999999999995,
                                        'it_average': [156.119, 234.234],
                                        'range_to_median': 0.10145948924283386,
                                        'all_average': 195.17650000000003},
                                   64: {'all_variance_to_mean': 29.198995681067522,
                                        'it_range_to_median': [0.666051278356643,
                                                               0.6434782608695652],
                                        'it_max': [444.111,
                                                   456.456],
                                        'it_variance': [12307.351598999998,
                                                        12345.654321000002],
                                        'it_range': [221.87699999999998,
                                                     222.222],
                                        'all_min': 222.234,
                                        'all_median': 339.23400000000004,
                                        'it_median': [333.123,
                                                      345.345],
                                        'min': 222.234,
                                        'all_variance': 9905.773884299999,
                                        'all_range_to_median': 0.6904437644811545,
                                        'max': 234,
                                        'all_range': 234.222,
                                        'variance': 69.21937799999989,
                                        'variance_to_mean': 0.30343805152619,
                                        'it_min': [222.234, 234.234],
                                        'all_max': 456.456,
                                        'it_variance_to_mean': [36.9417077855419,
                                                                35.74875652173913],
                                        'average': 228.11700000000002,
                                        'median': 228.11700000000002,
                                        'ops_per_sec': [222.234, 234],
                                        'ops_per_sec_values': [[222.234, 333.123, 444.111],
                                                               [234.234, 345.345, 456.456]],
                                        'range': 11.765999999999991,
                                        'it_average': [333.156, 345.345],
                                        'range_to_median': 0.05157879509199222,
                                        'all_average': 339.25050000000005}}}}}
        client = MultiEvergreenAnalysis()
        client.results = data
        client.aggregate_results()
        self.assertEqual(client.agg_results, expected)

    def test_main(self):
        """MultiEvergreenAnalysis: Fetch real Evergreen results and write output files."""
        #pylint: disable=no-self-use
        evergreen_config = test_utils.repo_root_file_path('config.yml')
        args = ['--evergreen-config', evergreen_config,
                '--json', '--out', 'test_outfile.json',
                '587773af3ff1220ab9000946', '587773b03ff1220ab900094a']
        main(args)
        # Intentionally not checking output files, just testing that we run without exceptions.

if __name__ == '__main__':
    unittest.main()
