"""Unit tests for validating override files."""

import unittest

from evergreen import override


class TestValidate(unittest.TestCase):
    """Test `validation()`."""

    def setUp(self):
        """Instantiate a valid override dictionary in `self.override`."""

        self.override = {
            "variant": {
                "task": {
                    "threshold": {
                        "test": {
                            "thread_threshold": 1,
                            "ticket": ["BF-3"],
                            "threshold": 1
                        }
                    }
                }
            }
        }

    def test_successful_validation(self):
        """Successfully validate a correct override dictionary."""

        try:
            override.validate(self.override)

        except AssertionError as err:
            self.fail(
                "Failed to validate correct override file with the following error: `{}`".format(
                    err))

    def test_empty_override(self):
        """Fail validation when a variant or task is empty."""

        self.override["variant"] = {}
        self._test_validation_fail()
        self.override["variant"]["task"] = {}
        self._test_validation_fail()

    def test_missing_override_type(self):
        """Fail validation when missing an override_type."""

        del self.override["variant"]["task"]["threshold"]
        self._test_validation_fail()

    def test_missing_test_override_key(self):
        """Fail validation when missing a required key in an override."""

        del self.override["variant"]["task"]["threshold"]["test"]["ticket"]
        self._test_validation_fail()

    def test_bad_ticket_name(self):
        """Fail when an invalid ticket name is found."""

        self.override["variant"]["task"]["threshold"]["test"]["ticket"] = ["bad-ticket-name"]
        self._test_validation_fail()

    def test_bad_threshold(self):
        """Fail validation when \"threshold\" overrides are missing required keys."""

        del self.override["variant"]["task"]["threshold"]["test"]["thread_threshold"]
        self._test_validation_fail()
        self.setUp()
        del self.override["variant"]["task"]["threshold"]["test"]["ticket"]
        self._test_validation_fail()

    def _test_validation_fail(self):
        with self.assertRaises(AssertionError):
            override.validate(self.override)


if __name__ == "__main__":
    unittest.main()
