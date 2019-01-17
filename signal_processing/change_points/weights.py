"""
Functions to generate weights that can be used to grow or decay series values.
"""
import numpy as np
from scipy.stats import expon

DEFAULT_WEIGHTING = .001
"""
The default value to use to generate the weightings.
See :method:`linear_weights` and `exponential_weights` for more details.
"""


def linear_weights(size, weighting):
    """
    Create an array of linearly decaying values. The calling code should flip the return value if
    required.

    :param int size: The length of the generated weights array.
    :param weighting: The percentage difference between points.
    :return: An array of weights to multiply against the values to grow or decay them.
    :rtype: list(float).
    """
    weights = np.array([1 - weighting * i for i in range(size - 1, -1, -1)], dtype=np.float64)
    return weights


def exponential_weights(size, weighting):
    """
    Create an array of exponentially decaying values. The calling code should flip the return value
    if required.

    The values selected are from the formula:

        f(x) = exp(-x) # the probability density function for expon

    Some examples (the values produced are floats, they are expressed here as percentages for
    clarity):

        .001 weighting produces the following:

            100%  55% 30% 16% 9% 5% 2% 1.5% .8% .4$

            _So 100% of the first value is retained, 55% of the second and so on._

        .0001 weighting produces the following:

            100%  43% 19% 8% 3.6% 1.5% .6% .3% .1% .05$


        .1 * 100 weighting produces the following:

            100%  87% 76% 67% 59% 51% 45% 39% 34% 30$

    A lower weighting decays quickly and a higher weighting decays more slowly. This allows the
    points closer to the filtered or not.

    The logic behind this approach is that linear decay is constant so it is insensitive.
    Exponential decay allows a greater range / type of values to be generated depending on the
    exact value of weighting.

    :param int size: The length of the generated weights array.
    :param weighting: The percentage difference between points.
    :return: An array of weights to multiply against the values to grow or decay them.
    :rtype: list(float).

    See `expon<https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.expon.html>`
    See `ppf<https://en.wikipedia.org/wiki/Quantile_function>`.
    """
    # create at least 100 or size evenly spaced numbers from 1 to ppf(1 - weighting).
    # ppf is probability of the variable being less than or equal to that value.
    x = np.linspace(1.0, expon.ppf(1 - weighting), min(size, 100))
    random_variable = expon()

    # get the probability density variable for x and select every 10 element.
    pdf = random_variable.pdf(x)
    weights = pdf[0:min(size, 100) * 10:10]

    # normalize to start at 1 (weights[0] is the max value).
    weights = weights / weights[0]
    return weights
