"""
Set up logging for DSI scripts.
"""
from __future__ import print_function
from __future__ import absolute_import
import sys

import logging
from StringIO import StringIO
import structlog


def setup_logging(verbose=False, filename=None, explicit_log_level=None):
    """Configure logging verbosity and destination."""
    if explicit_log_level:
        loglevel = explicit_log_level
    else:
        loglevel = logging.DEBUG if verbose else logging.INFO
    handler = logging.FileHandler(filename) if filename else logging.StreamHandler()
    handler.setLevel(loglevel)
    root_logger = logging.getLogger()
    root_logger.setLevel(loglevel)
    root_logger.addHandler(handler)

    # The following sets the minimum level that we will see for the given component. So we will
    # only see warnings and higher for paramiko, boto3 and botocore. We will only see errors / fatal
    # / critical log messages for /dev/null
    logging.getLogger("paramiko").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("error_only").setLevel(logging.ERROR)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class IOLogAdapter(StringIO):
    """
    Adapter a logger instance to an IO interface.
    It derives from StringIO in order to get stubbed base implementations
    of methods like flush and close.
    """

    def __init__(self, logger, level=None):
        StringIO.__init__(self)
        self.logger = logger
        self.level = logging.INFO if not level else level

    def _barf_if_closed(self):
        """ raise an exception if this stream is closed. """
        if self.closed:
            raise ValueError("I/O operation on closed file")

    def write(self, s):
        """
        write a line to the logger at the specified level
        :param string s: the line to log, it is stripped first.

        :raises raise ValueError I/O operation on closed file
        """
        self._barf_if_closed()
        self.logger.log(self.level, s.rstrip())

    def writelines(self, iterable):
        """
        write the contents of iterable to the logger at the specified level
        :param iterable: the lines to log.

        :raises raise ValueError I/O operation on closed file
        """
        for line in iterable:
            self._barf_if_closed()
            self.write(line)


class UTF8WrapperStream(object):
    """
    Get around Python 2's terrible utf-8 handling.
    Wraps a delegate stream and any write* calls
    will first encode the value in utf-8 and ignore
    any conversion errors.

    This hopefully goes away when DSI moves to Python 3.
    """

    def __init__(self, child):
        """
        :param child: child io-stream or file-like object.
        """
        self._child = child
        if sys.version_info[0] > 2:
            # can't rely on logging yet!
            sys.stderr.write("UTF8WrapperStream is only necessary in Python versions prior to 3.0")

    def write(self, line):
        """Write to the underlying stream first converting to utf-8."""
        self._child.write(line.encode("utf-8", "ignore"))
        # ignore means ignore any characters can't couldn't be converted to
        # utf-8 and continue on with the rest
        # https://docs.python.org/2/library/codecs.html#codec-base-classes

    def writelines(self, lines):
        """Write lines. See write()."""
        for line in lines:
            self.write(line)

    def flush(self):
        """Pass-through to child.flush()"""
        self._child.flush()

    def close(self):
        """Pass-through to child.close()"""
        self._child.close()


class TeeStream(object):
    """ A class type to tee output to multiple streams
    Only write, writelines, flush and close are supported. Add more
    method if necessary.

    Nothing is returned by any of the methods and they will raise exceptions
    as defined by the 'streams'. So for example, calling close multiple times
    shouldn't raise exceptions but writing to a closed stream probably will.

    The following example would write stdout to filename *and* info logger and
    writes stderr to filename and error logger:

        with open(filename, 'w+', 0) as out:
            tee_out = TeeStream(INFO_ADAPTER, out)
            tee_err = TeeStream(ERROR_ADAPTER, out)
            host.exec_command(command, out=tee_out, err=tee_err, pty=True)

            tee_out.flush()
            tee_out.close()

            tee_err.flush()
            tee_err.close()

    :param stream: the streams to write to
    :type streams: iterable, array, tuple

    :see https://docs.python.org/2/library/io.html#io.IOBase for the
    interface it should implement.
    """

    def __init__(self, *streams):
        self.streams = list(streams)
        self.closed = False

    def write(self, line):
        """
        write line to all streams
        :param line: the line to write
        :type  line: string
        """
        for stream in self.streams:
            stream.write(line)

    def writelines(self, iterable):
        """
        write the contents of iterable to all streams (each line is written to
        each stream in turn)
        :param iterable: the lines to write
        :type  iterable: array, iter, generator .. something iterable
        """
        for line in iterable:
            for stream in self.streams:
                stream.write(line)

    def flush(self):
        """
        flush each stream in turn
        """
        for stream in self.streams:
            stream.flush()

    def close(self):
        """
        close each stream in turn
        """
        self.closed = True
        for stream in self.streams:
            stream.close()
