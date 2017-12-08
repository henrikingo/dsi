"""
Utility function.
"""
import os
import errno


def mkdir_p(path):
    """ make the directory and all missing parents (like mkdir -p)
    :type path: string the directory path
    """
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def touch(filename):
    """ create an empty file (like shell touch command). It will not
    create directories
    :type filename: string the full path to the filename
    """
    open(filename, 'a').close()
