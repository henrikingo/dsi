"""
Common Job helpers and objects.
"""
import multiprocessing
import signal
import sys
import traceback
from StringIO import StringIO
import copy_reg
import types

# pylint: disable=too-many-instance-attributes,too-many-arguments,too-few-public-methods
from contextlib import contextmanager
from datetime import datetime

from bson.json_util import dumps
import pymongo
import structlog

import click

LOG = structlog.getLogger(__name__)


def _pickle_method(method):
    """
    A functions for pickling a method.

    :param object method: The instance method reference.
    See 'pickle instancemethods
    <https://bytes.com/topic/python/answers/552476-why-cant-you-pickle-instancemethods>'.
    """
    func_name = method.im_func.__name__
    obj = method.im_self
    cls = method.im_class
    return _unpickle_method, (func_name, obj, cls)


def _unpickle_method(func_name, obj, cls):
    """
    A functions for unpickling a method.

    :param str func_name: The instance method name.
    :param object obj: The object instance reference.
    :param object cls: The object class reference.
    See 'pickle instancemethods
    <https://bytes.com/topic/python/answers/552476-why-cant-you-pickle-instancemethods>'.
    """
    for clazz in cls.mro():
        try:
            func = clazz.__dict__[func_name]
        except KeyError:
            pass
        else:
            break
    return func.__get__(obj, cls)


# register the pickle functions for MethodType
copy_reg.pickle(types.MethodType, _pickle_method, _unpickle_method)


class Job(object):
    """
    Encapsulate a job.

    When called as a function, it executes the wrapped function. That is:

           self.return_value = self.function_reference(*self.function_arguments, **self.kwargs)

    In addition it will set:
       *complete* to True (once the function has returned or has thrown an exception).
       *result* is set to the return of the function id exception is None and complete is
       True
       *exception* is set if an exception was thrown and complete is True.
       *duration* is set if complete is True.
    """

    # pylint: disable=too-few-public-methods,too-many-arguments
    def __init__(self, function_reference, arguments=(), kwargs=None, identifier=None):
        """
        Create a call to evaluate a method or function.

        :param function_reference: The function or method to call.
        :type function_reference: method or function.
        :param tuple arguments: The function arguments.
        :param dict kwargs: The keyword arguments for the function.
        :param object identifier: An identifier for this job. It doesn't have to be unique.
        """
        self._duration = None
        self.created_at = None
        self.started_at = None
        self.ended_at = None

        self.result = None
        self.exception = None

        self.function_reference = function_reference
        if isinstance(open, types.MethodType):
            self.function_name = self.function_reference.func_name
        else:
            self.function_name = self.function_reference.__name__

        self.function_arguments = arguments

        self.kwargs = kwargs
        if identifier is not None:
            self.identifier = identifier
        else:
            self.identifier = self.__repr__()

    @property
    def duration(self):
        """
        Get the job duration.

        :return: The number of seconds duration.
        see :method: `timedelta.total_seconds`.
        """
        if self._duration is None:
            if self.complete:
                self._duration = (self.ended_at - self.started_at).total_seconds()
        return self._duration

    @property
    def complete(self):
        """
        Is the job complete.

        :return: True if the job has completed.
        """
        return self.ended_at is not None and self.started_at is not None

    def __call__(self):
        """
        Execute the wrapped function.

        :return: This job instance.
        """
        self.started_at = datetime.utcnow()
        LOG.debug(
            "job started",
            identifier=self.identifier,
            arguments=self.function_arguments,
            kwargs=self.kwargs,
            started_at=self.started_at.isoformat())
        try:
            kwargs = self.kwargs if self.kwargs is not None else {}
            arguments = self.function_arguments if self.function_arguments is not None else []
            self.result = self.function_reference(*arguments, **kwargs)
        except pymongo.errors.PyMongoError as pme:
            # Setting `self.exception=pme` causes errors, see TIG-1689.
            # This seems to match the behaviour described
            # http://api.mongodb.com/python/current/faq.html#id3
            # Multiprocessing uses forks / locks and threads. I suspect pymongo Exceptions must
            # be keeping a reference to the mongo client and if a lock is invalid then reading
            # the exception details from the socket would not be correct.
            # The actual error manifests as the 'details' being a string instance (rather than a
            # dict), this case appears to be otherwise impossible.

            # pylint: disable=no-member
            details = getattr(pme, 'details') if hasattr(pme, 'details') else {}
            full_name = str(pme.__module__) + '.' + str(pme.__class__.__name__)

            LOG.warn(
                "error in function call",
                function=self.function_reference,
                arguments=self.function_arguments,
                exc_info=1,
                details=details,
                full_name=full_name)

            e = "\n".join((full_name, dumps(details, indent=4, sort_keys=True) if details else '',
                           traceback.format_exc()))
            self.exception = Exception(e)
        except Exception as e:  # pylint: disable=broad-except
            LOG.warn(
                "error in function call",
                function=self.function_reference,
                arguments=self.function_arguments,
                exc_info=1)
            self.exception = e

        self.ended_at = datetime.utcnow()
        LOG.debug(
            "job completed",
            identifier=self.identifier,
            function=self.function_reference,
            function_arguments=self.function_arguments,
            kwargs=self.kwargs,
            return_value=self.result,
            exception=self.exception.__repr__() if self.exception is not None else None,
            started_at=self.started_at.isoformat(),
            ended_at=self.ended_at.isoformat(),
            duration=self.duration)

        return self

    def __str__(self):
        """
        Get a readable string for this job.

        :returns: A readable string.
        """
        return "{} {}".format(self.identifier, self.exception if self.complete else '').rstrip()

    def __repr__(self):
        """
        Get an unambiguous string for this job.

        :returns: An unambiguous string.
        """
        return "{module}.{function}({arguments}{kwargs}) {exception}".format(
            module=self.function_reference.__module__,
            function=self.function_name,
            arguments=self.function_arguments if self.function_arguments else '',
            kwargs=',{}'.format(self.kwargs) if self.kwargs is not None else '',
            exception=self.exception.__repr__() if self.complete else '').rstrip()


@contextmanager
def pool_manager(job_list, pool_size):
    """
    A context manager to handle creating and cleaning up the process pool. Multiprocess or single
    process is also handled.

    Note: when Multiprocess implementation is in use the input list and the output list can be
    different. This is because the Job is marshaled to the subprocess and then a new copy is
    returned with the completed, exception and status fields set.

    So if you want to get the return values outside the context manager you must keep a reference
    to them.

    For example:

        import time
        job_list = [Job(time.sleep, arguments=(i / 5.0, )) for i in range(10)]
        completed_jobs = []
        with pool_manager(job_list, pool_size) as job_iterator:
            for job in progress:
                completed_jobs.append(job)

        # job_list would not work in this case as this is the original job before it
        # is evaluated
        return [job for job in completed_jobs if job.exception is not None]


    :param list(callable) job_list: The list of jobs to execute.
    :param int pool_size: The number of processes to map the jobs across. 1 implies the
    current process, this is useful for debugging.

    :return: A job_iterator, you need to iterate over theis list to  get the single process
    version to evaluate the results.
    """
    # result only after one of the tasks completes.
    #
    # For multiprocessing, imap_unordered provides this behavior.
    # In the single process case :method: `jobs.async_job_runner_adapter` and
    # :method: `jobs.async_job_runner` provides this behavior.
    pool = None
    if pool_size is not None and pool_size >= 1:
        original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        pool = multiprocessing.Pool(processes=pool_size)
        signal.signal(signal.SIGINT, original_sigint_handler)
        job_iterator = pool.imap_unordered(async_job_runner, job_list)
    else:
        job_iterator = async_job_runner_adapter(job_list)

    try:
        yield job_iterator
    except KeyboardInterrupt:
        LOG.warn("Caught KeyboardInterrupt, terminating workers")
        if pool:
            pool.terminate()
    finally:
        if pool:
            pool.close()
            pool.join()


def async_job_runner(job):
    """
    multiprocessing.Pool.imap_unordered requires a function and a list of parameters, This function
    simply invokes job as a function with no parameters.

    :param callable job: The callable reference.
    :return: The return type of job.
    See method `multiprocessing.Pool.imap_unordered`.
    """
    return job()


def async_job_runner_adapter(jobs):
    """
    A generator to make single process (pool size is 1) implementations work the same way as
    multi process versions.

    :param list jobs: The list  of callable instances.
    :return: Yields the return of each callable invocation.
    See method `multiprocessing.Pool.imap_unordered`.
    """
    for job in jobs:
        yield job()


def process_jobs(jobs,
                 pool_size=None,
                 label='starting',
                 progressbar=False,
                 bar_template=None,
                 show_item=None,
                 key=None):
    """
    Process the list of jobs. If pool_size is 0 or none then the jobs are processed inline in a
    single process. All other cases will involve creating a pool work processes and executing the
    jobs in the sub processes.

    If progressbar is True then a progressbar is rendered on stderr  otherwise no progress bar is
    rendered.

    Note: a progress bar is also not rendered if stderr is not a tty.
    Note: jobs and the list of completed jobs will only be the same if the jobs are processed
    inline. This is due to the fact that a copy of the job is sent to the subprocess and then
    another copy (containing the results / expceptions/ duration etc.) is returned to the calling
    process.

    :param list jobs: The list  of callable instances.
    :param int pool_size: The process pool size.
    :param str label: The starting label for the progress bar.
    :param str key: The key identifier.
    :param str bar_template: The progressbar template.
    :param callable show_item: A function to format the progressbar item.
    :param bool progressbar: Render the progressbar if this is set to True.
    :return: A list of completed jobs.
    """
    completed_jobs = []
    with pool_manager(jobs, pool_size) as job_iterator:
        with click.progressbar(job_iterator,
                               length=len(jobs),
                               label=label,
                               item_show_func=show_item,
                               file=sys.stderr if progressbar else StringIO(),
                               bar_template=bar_template) as progress: # yapf: disable
            for job in progress:
                completed_jobs.append(job)
                identifier = job.identifier[key] if key else job.identifier
                if job.exception is None:
                    status = identifier
                else:
                    status = 'Exception: {} {}'.format(identifier, job.exception)
                progress.label = status
                progress.render_progress()
    return completed_jobs


def handle_exceptions(context, exceptions, logfile):
    """
    Handle jobs with exceptions in a consistent fashion for the CLI. This function does nothing
    if exceptions is empty.

    :param list(Jobs) exceptions: A list of jobs containing exceptions.
    :param click.Context context: The click context.
    :param str logfile: The log file location.
    :raises: click.UsageError if exceptions is not empty
    """
    if exceptions:
        message = '{} Unexpected Exceptions(see {} for details).'.format(len(exceptions), logfile)
        LOG.warn(message, exceptions=exceptions)
        context.fail("{}\n{}".format(message,
                                     "\n".join(["\t{!r}".format(job) for job in exceptions])))
