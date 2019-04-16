"""
A class to contain and scope common test helper functions.
"""

#pylint: disable=too-few-public-methods
from mock import MagicMock


class Helpers(object):
    """
    Contain test helper functions.
    """

    def __init__(self):
        pass

    @staticmethod
    def create_test_identifier(project=None, variant=None, task=None, test=None, thread_level=None):
        """
        create a test identifier for use in a test method.
        :param project: The project name. None implies sys-perf.
        :param variant: The variant name. None implies linux-1-node-replSet.
        :param task: The task name. None implies bestbuy_agg.
        :param test: The test name. None implies 15_5c_update.
        :param thread_level: The thread level. None implies 60.
        :return: A test identifier dict.
        """
        return {
            'project': 'sys-perf' if project is None else project,
            'variant': 'linux-1-node-replSet' if variant is None else variant,
            'task': 'bestbuy_agg' if task is None else task,
            'test': '15_5c_update' if test is None else test,
            'thread_level': '60' if thread_level is None else thread_level
        }

    @staticmethod
    def create_mock_task_rejector(results=None,
                                  is_patch=False,
                                  order=None,
                                  latest=None,
                                  rejected=None):
        """
        Create a mock task rejector.
        :param results: The test results.
        :param is_patch: True if this is a patch result set.
        :param order: The revision order/
        :param latest: Is this the latest order.
        :param rejected: Is this rejected.
        :return: A mock task rejector.
        """
        if results is None:
            results = []
        kwargs = dict(name='task_rejector', results=results, patch=is_patch)
        if order is not None:
            kwargs['order'] = order
        if latest is not None:
            kwargs['latest'] = latest
        if rejected is not None:
            kwargs['rejected'] = rejected
        return MagicMock(**kwargs)
