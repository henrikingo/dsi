"""
Set up logging for DSI scripts.
"""
import logging


def setup_logging(verbose, filename=None):
    """Configure logging verbosity and destination."""
    loglevel = logging.DEBUG if verbose else logging.INFO
    if filename:
        handler = logging.FileHandler(filename)
    else:
        handler = logging.StreamHandler()
    handler.setLevel(loglevel)
    handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    root_logger = logging.getLogger()
    root_logger.setLevel(loglevel)
    root_logger.addHandler(handler)
    # we don't want to see info from paramiko
    logging.getLogger('paramiko').setLevel(logging.WARNING)
