"""
Unit tests for signal_processing/helpers.py.
"""
import time
import unittest

import mock
from mock import patch

import signal_processing.commands.jobs as jobs


def _create_job(exception=None, arguments=('arguments', ), kwargs=None):
    if kwargs is None:
        kwargs = {'thing': 1, 'that': 'other'}
    mock_function = mock.MagicMock(
        name='dummy function', return_value='return', __name__='dummy function')
    if exception is not None:
        mock_function.side_effect = exception
    job = jobs.Job(
        mock_function,
        arguments=arguments,
        kwargs=kwargs,
        identifier='identifier') #yapf: disable
    return job


class TestJob(unittest.TestCase):
    """
    Test Job.
    """

    def test_before_call(self):
        """ Test before call."""
        job = _create_job()
        self.assertFalse(job.complete)
        self.assertIsNone(job.result)
        self.assertIsNone(job.exception)

    def test_call(self):
        """ Test successful call."""
        job = _create_job()
        job()
        self.assertTrue(job.complete)
        self.assertEquals('return', job.result)
        self.assertIsNone(job.exception)

    def test_exception(self):
        """ Test exception."""
        exception = Exception('exception')
        job = _create_job(exception=exception)
        job()
        self.assertTrue(job.complete)
        self.assertIsNone(job.result)
        self.assertEqual(exception, job.exception)

    def test_none_arguments(self):
        """
        Test job execution None arguments.
        """
        job = _create_job(arguments=None)
        job()
        self.assertTrue(job.complete)
        self.assertIsNotNone(job.result)

    def test_empty_arguments(self):
        """
        Test job execution empty arguments.
        """
        job = _create_job(arguments=[])
        job()
        self.assertTrue(job.complete)
        self.assertIsNotNone(job.result)

    def test_none_kwargs(self):
        """
        Test job execution None kwargs.
        """
        job = _create_job(kwargs=None)
        job()
        self.assertTrue(job.complete)
        self.assertIsNotNone(job.result)

    def test_empty_kwargs(self):
        """
        Test job execution empty kwargs.
        """
        job = _create_job(kwargs={})
        job()
        self.assertTrue(job.complete)
        self.assertIsNotNone(job.result)


class TestPoolManager(unittest.TestCase):
    """
    Test pool_manager.
    """

    def _test_helper(self, job_list=(), pool_size=0):
        with patch('multiprocessing.Pool') as mock_pool_cls, \
             patch('signal_processing.commands.jobs.async_job_runner_adapter')\
                     as mock_async_job_runner_adapter:
            mock_pool = mock.MagicMock(name='dummy function', return_value='return')
            mock_pool_cls.return_value = mock_pool
            mock_pool.imap_unordered.return_value = 'imap_unordered'
            mock_async_job_runner_adapter.return_value = 'adapter'
            with jobs.pool_manager(job_list, pool_size) as iterator:
                pass

            if pool_size == 0:
                self.assertEqual('adapter', iterator)
                mock_pool_cls.assert_not_called()
                mock_async_job_runner_adapter.assert_called_once_with(job_list)
            else:
                self.assertEqual('imap_unordered', iterator)
                mock_pool_cls.assert_called_once_with(processes=pool_size)
                mock_pool.imap_unordered.assert_called_once_with(jobs.async_job_runner, job_list)
                mock_pool.close.assert_called_once()
                mock_pool.join.assert_called_once()
                mock_async_job_runner_adapter.assert_not_called()

    def test_single(self):
        """ Test pool size 1."""
        self._test_helper()

    def test_multiple(self):
        """ Test pool size 2."""
        self._test_helper(pool_size=2)


class TestAsyncJobRunner(unittest.TestCase):
    """
    Test async_job_runner.
    """

    def test_async_job_runner(self):
        mock_function = mock.MagicMock(name='dummy function', return_value='return')
        self.assertEqual('return', jobs.async_job_runner(mock_function))
        mock_function.assert_called_once_with()


class TestAsyncJobRunnerAdapter(unittest.TestCase):
    """
    Test async_job_runner_adapter.
    """

    def test_async_job_runner(self):
        expected = ['return1', 'return2']
        mock_functions = [mock.MagicMock(name=name, return_value=name) for name in expected]
        actual = [result for result in jobs.async_job_runner_adapter(mock_functions)]
        self.assertEqual(expected, actual)
        for mock_function in mock_functions:
            mock_function.assert_called_once_with()


class TestProcessJobs(unittest.TestCase):
    """
    Test process_jobs.
    """

    def test_process_jobs_empty(self):
        """
        Test process_jobs empty jobs list.
        """
        with patch('signal_processing.commands.jobs.pool_manager') as mock_pool_manager:
            mock_pool_manager.return_value.__enter__.return_value = ()
            self.assertEqual([], jobs.process_jobs([]))

    def test_process_with_jobs(self):
        """
        Test process_jobs with jobs.
        """
        job_list = [jobs.Job(time.sleep)]
        with patch('signal_processing.commands.jobs.pool_manager') as mock_pool_manager:
            mock_pool_manager.return_value.__enter__.return_value = job_list
            self.assertEqual(job_list, jobs.process_jobs(job_list))

    def test_process_with_exceptions(self):
        """
        Test process_jobs with exceptions.
        """
        job_list = [jobs.Job(time.sleep), jobs.Job(time.sleep)]
        job_list[1].exception = Exception('boom')
        with patch('signal_processing.commands.jobs.pool_manager') as mock_pool_manager, \
             patch('click.progressbar') as mock_progressbar:
            mock_pool_manager.return_value.__enter__.return_value = job_list
            mock_progressbar.return_value.__enter__.return_value = mock_progressbar
            mock_progressbar.__iter__ = mock.MagicMock(return_value=iter(job_list))
            self.assertEqual(job_list, jobs.process_jobs(job_list))
        self.assertIn('Exception: time.sleep() boom', mock_progressbar.label)
