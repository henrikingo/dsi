"""Unit tests for `evergreen.override`."""

import unittest

from evergreen import override # pylint: disable=import-error

class TestValidate(unittest.TestCase):
    """Test `validation()`."""

    def setUp(self):
        """Instantiate a valid override dictionary in `self.override`."""

        self.override = {
            "variant": {
                "reference": {
                    "test": {
                        "results": {
                            "1": {
                                "ops_per_sec": 1
                            }
                        },
                        "threads": None,
                        "ticket": ["SERVER-1"],
                        "revision": None
                    }
                },
                "ndays": {
                    "test": {
                        "create_time": "foo",
                        "results": {
                            "1": {
                                "ops_per_sec": 1
                            }
                        },
                        "threads": None,
                        "ticket": ["PERF-2"],
                        "revision": None
                    }
                },
                "threshold": {
                    "test": {
                        "thread_threshold": 1,
                        "ticket": ["BF-3"],
                        "threshold": 1
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
        """Fail validation when missing a variant override."""

        self.override["variant"] = {}
        self._test_validation_fail()

    def test_missing_override_type(self):
        """Fail validation when missing an override_type."""

        del self.override["variant"]["reference"]
        self._test_validation_fail()

    def test_missing_test_override_key(self):
        """Fail validation when missing a required key in an override."""

        del self.override["variant"]["reference"]["test"]["ticket"]
        self._test_validation_fail()
        self.setUp()
        del self.override["variant"]["ndays"]["test"]["create_time"]
        self._test_validation_fail()

    def test_missing_thread_override(self):
        """Fail validation when \"results\" is empty."""

        self.override["variant"]["reference"]["test"]["results"] = {}
        self._test_validation_fail()

    def test_bad_ticket_name(self):
        """Fail when an invalid ticket name is found."""

        self.override["variant"]["reference"]["test"]["ticket"] = ["bad-ticket-name"]
        self._test_validation_fail()

    def test_bad_threshold(self):
        """Fail validation when \"threshold\" overrides are missing required keys."""

        del self.override["variant"]["threshold"]["test"]["thread_threshold"]
        self._test_validation_fail()
        self.setUp()
        del self.override["variant"]["threshold"]["test"]["ticket"]
        self._test_validation_fail()

    def _test_validation_fail(self):
        with self.assertRaises(AssertionError):
            override.validate(self.override)

if __name__ == "__main__":
    unittest.main()
