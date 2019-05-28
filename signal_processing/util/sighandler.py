"""Utility to support asynchronously signaling the current process."""

import signal
import sys
import traceback


def register(logger):
    """
    Register an event object to wait for signal, or a signal handle for SIGUSER1.

    :param logger: Logger to print stacks to.
    """

    def _handle_sigusr1(signum, frame):  # pylint: disable=unused-argument
        """
        Signal handler for SIGUSR1.

        The handler will dump the stacks of all threads and write out the report file and
        log suite summaries.

        :param signum: unused.
        :param frame: unused.
        """
        header_msg = "Dumping stacks due to SIGUSR1 signal"
        _dump_stacks(logger, header_msg)

    signal.signal(signal.SIGUSR1, _handle_sigusr1)


def _dump_stacks(logger, header_msg):
    """
    Signal handler that will dump the stacks of all threads.

    :param logger: Logger to print to.
    :param header_msg: Header message to include
    """

    frames = sys._current_frames()  # pylint: disable=protected-access
    logger.info(header_msg, total_threads=len(frames))

    for thread_id in frames:
        stacktrace = "".join(traceback.format_stack(frames[thread_id]))
        logger.info("stacktrace", thread_id=thread_id, frame=stacktrace)
