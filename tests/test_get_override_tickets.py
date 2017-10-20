"""
Unit tests for `get_override_tickets.py`.
"""

import unittest
import StringIO

import get_override_tickets
from tests import test_utils


class TestPerfRegressionCheck(unittest.TestCase):
    """Test suite."""

    def runTest(self):
        """
        Run the script and compare the file it generates to an expected one.
        """

        for rule in ["all", "threshold", "reference"]:
            for override_type in ["perf", "system_perf"]:
                override_filename = override_type + "_override.json"
                args = ["-r", rule, "-f", test_utils.fixture_file_path(override_filename)]
                script_output_str = StringIO.StringIO()
                with test_utils.redirect_stdout(script_output_str):
                    get_override_tickets.main(args)

                reference_file_path = test_utils.fixture_file_path("tickets.{}.{}.out.ok".format(
                    override_type, rule))

                with open(reference_file_path) as reference_file:
                    reference_str = reference_file.read()

                err_msg = 'Incorrect script output for rule "{}" and type "{}".'.format(
                    rule, override_type)
                print "Test result:\n{}\n\nExpected:\n{}".format(script_output_str.getvalue(),
                                                                 reference_str)
                self.assertEqual(script_output_str.getvalue(), reference_str, err_msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
