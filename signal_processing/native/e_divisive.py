"""
Wrap a C library function to calculate E-Divisive qhat values with
input using the numpy.ctypeslib.
"""

from ctypes import c_int

import numpy as np
import numpy.ctypeslib as npct
import os
import structlog

LOG = structlog.getLogger(__name__)

LOADED = False
"""
A flag indicating if the native library was found. Pessimistically set to False.
"""


def qhat_values_wrapper(series, qhat_values, diffs):  # pylint: disable=unused-argument
    """
    This defines a qhat_func that raises an ImportError.

    :param np.array(float) series: The series data.
    :raises: ImportError is always raised by this function.
    """
    raise ImportError("E-Divisive native failed to load.")


def qhat_diffs_wrapper(series):  # pylint: disable=unused-argument
    """
    A wrapper function to marshall the parameters and call the native qhat_values function.

    :param np.array(float) series: The series data.
    :param np.2darray(float) diffs: The diffs matrix.
    :param np.array(float) qhat_values: The array to store the qhat values.
    :return: The calculated qhat values.
    :rtype: np.array(float).
    :raises: Exception if the native function doesn't return 0.
    """
    raise ImportError("E-Divisive native failed to load.")


try:
    so_path = os.path.dirname(os.path.abspath(__file__))

    # input type for the cos_doubles function
    # must be a double array, with single dimension that is contiguous
    ARRAY_DOUBLE = npct.ndpointer(dtype=np.double, ndim=1, flags='CONTIGUOUS')
    MATRIX_DOUBLE = npct.ndpointer(dtype=np.double, ndim=2, flags='CONTIGUOUS')

    # load the library, using numpy mechanisms
    LIB_E_DIVISIVE = npct.load_library("_e_divisive", so_path)

    # setup the return types and argument types
    LIB_E_DIVISIVE.qhat_values.restype = c_int
    LIB_E_DIVISIVE.qhat_values.argtypes = [ARRAY_DOUBLE, MATRIX_DOUBLE, ARRAY_DOUBLE, c_int]

    # setup the return types and argument types
    LIB_E_DIVISIVE.calculate_diffs.restype = c_int
    LIB_E_DIVISIVE.calculate_diffs.argtypes = [ARRAY_DOUBLE, MATRIX_DOUBLE, c_int]

    def qhat_values_wrapper(series, diffs, qhat_values):  # pylint: disable=E0102
        """
        A wrapper function to marshall the parameters and call the native qhat_values function.

        :param np.array(float) series: The series data.
        :param np.2darray(float) diffs: The diffs matrix.
        :param np.array(float) qhat_values: The array to store the qhat values.
        :return: The calculated qhat values.
        :rtype: np.array(float).
        :raises: Exception if the native function doesn't return 0.
        """
        size = len(series)
        result = LIB_E_DIVISIVE.qhat_values(series, diffs, qhat_values, size)
        if result != 0:
            raise Exception("Native E-Divisive returned unexpected value {}".format(result))

        return qhat_values

    def qhat_diffs_wrapper(series):  # pylint: disable=E0102
        """
        A wrapper function to marshall the parameters and call the native qhat_values function.

        :param np.array(float) series: The series data.
        :param np.2darray(float) diffs: The diffs matrix.
        :param np.array(float) qhat_values: The array to store the qhat values.
        :return: The calculated qhat values.
        :rtype: np.array(float).
        :raises: Exception if the native function doesn't return 0.
        """
        size = len(series)
        diffs = np.zeros((size, size), dtype=np.float)
        result = LIB_E_DIVISIVE.calculate_diffs(series, diffs, size)
        if result != 0:
            raise Exception("Native E-Divisive returned unexpected value {}".format(result))

        return diffs

    LOADED = True
except:  # pylint: disable=bare-except
    LOG.warn("native E-Divisive", loaded=False, so_path=so_path, exc_info=1)
