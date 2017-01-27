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
                                                                'ops_per_sec_values': [111.123]},
                                                         '64': {'ops_per_sec': 222.234,
                                                                'ops_per_sec_values': [222.234]}
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
                                                                'ops_per_sec_values': [123]},
                                                         '64': {'ops_per_sec': 234,
                                                                'ops_per_sec_values': [234]}
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
                                       {'all_variance_to_mean': 0.3012585884342843,
                                        'it_range_to_median': [0.0, 0.0],
                                        'it_max': [111.123, 123.0],
                                        'it_variance': [0.0, 0.0],
                                        'it_range': [0.0, 0.0],
                                        'all_min': 111.123,
                                        'all_median': 117.0615,
                                        'it_median': [111.123, 123.0],
                                        'min': 111.123,
                                        'all_variance': 35.26578224999997,
                                        'all_range_to_median': 0.10145948924283386,
                                        'max': 123, 'all_range': 11.876999999999995,
                                        'variance': 35.26578224999997,
                                        'variance_to_mean': 0.3012585884342843,
                                        'it_min': [111.123, 123.0],
                                        'all_max': 123.0,
                                        'it_variance_to_mean': [0.0, 0.0],
                                        'average': 117.0615,
                                        'median': 117.0615,
                                        'ops_per_sec': [111.123, 123],
                                        'ops_per_sec_values': [[111.123], [123]],
                                        'range': 11.876999999999995,
                                        'it_average': [111.123, 123.0],
                                        'range_to_median': 0.10145948924283386,
                                        'all_average': 117.0615},
                                   64: {'all_variance_to_mean': 0.151719025763095,
                                        'it_range_to_median': [0.0, 0.0],
                                        'it_max': [222.234, 234.0],
                                        'it_variance': [0.0, 0.0],
                                        'it_range': [0.0, 0.0],
                                        'all_min': 222.234,
                                        'all_median': 228.11700000000002,
                                        'it_median': [222.234, 234.0],
                                        'min': 222.234,
                                        'all_variance': 34.609688999999946,
                                        'all_range_to_median': 0.05157879509199222,
                                        'max': 234,
                                        'all_range': 11.765999999999991,
                                        'variance': 34.609688999999946,
                                        'variance_to_mean': 0.151719025763095,
                                        'it_min': [222.234, 234.0],
                                        'all_max': 234.0,
                                        'it_variance_to_mean': [0.0, 0.0],
                                        'average': 228.11700000000002,
                                        'median': 228.11700000000002,
                                        'ops_per_sec': [222.234, 234],
                                        'ops_per_sec_values': [[222.234], [234]],
                                        'range': 11.765999999999991,
                                        'it_average': [222.234, 234.0],
                                        'range_to_median': 0.05157879509199222,
                                        'all_average': 228.11700000000002}
                                  }
                             }
                        }
                   }
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
