"""
Set up logging for DSI scripts.
"""
import logging
from StringIO import StringIO


def setup_logging(verbose, filename=None):
    """Configure logging verbosity and destination."""
    loglevel = logging.DEBUG if verbose else logging.INFO
    handler = logging.FileHandler(filename) if filename else logging.StreamHandler()
    handler.setLevel(loglevel)
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    root_logger = logging.getLogger()
    root_logger.setLevel(loglevel)
    root_logger.addHandler(handler)
    # we don't want to see info from paramiko
    logging.getLogger('paramiko').setLevel(logging.WARNING)


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
