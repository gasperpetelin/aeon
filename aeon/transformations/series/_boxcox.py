"""Box-Cox transformation."""

__maintainer__ = ["TonyBagnall"]
__all__ = ["BoxCoxTransformer"]

import numpy as np
from scipy import optimize, special, stats
from scipy.special import boxcox, inv_boxcox
from scipy.stats import boxcox_llf, distributions, variation

from aeon.transformations.series.base import BaseSeriesTransformer
from aeon.utils.validation import is_int


# copy-pasted from scipy 1.7.3 since it moved in 1.8.0 and broke this estimator
def _calc_uniform_order_statistic_medians(n):
    """Approximations of uniform order statistic medians.

    Parameters
    ----------
    n : int
        Sample size.

    Returns
    -------
    v : 1d float array
        Approximations of the order statistic medians.

    References
    ----------
    .. [1] James J. Filliben, "The Probability Plot Correlation Coefficient
           Test for Normality", Technometrics, Vol. 17, pp. 111-117, 1975.
    """
    v = np.empty(n, dtype=np.float64)
    v[-1] = 0.5 ** (1.0 / n)
    v[0] = 1 - v[-1]
    i = np.arange(2, n)
    v[1:-1] = (i - 0.3175) / (n + 0.365)
    return v


class BoxCoxTransformer(BaseSeriesTransformer):
    r"""Box-Cox power transform.

    Box-Cox transformation is a power transformation that is used to
    make data more normally distributed and stabilize its variance based
    on the hyperparameter lambda. [1]_

    The _BoxCoxTransformer solves for the lambda parameter used in the Box-Cox
    transformation given `method`, the optimization approach, and input
    data provided to `fit`. The use of Guerrero's method for solving for lambda
    requires the seasonal periodicity, `sp` be provided. [2]_

    Parameters
    ----------
    bounds : tuple
        Lower and upper bounds used to restrict the feasible range
        when solving for the value of lambda.
    method : {"pearsonr", "mle", "all", "guerrero"}, default="mle"
        The optimization approach used to determine the lambda value used
        in the Box-Cox transformation.
    sp : int
        Seasonal periodicity of the data in integer form. Only used if
        method="guerrero" is chosen. Must be an integer >= 2.

    Attributes
    ----------
    bounds : tuple
        Lower and upper bounds used to restrict the feasible range when
        solving for lambda.
    method : str
        Optimization approach used to solve for lambda. One of "personr",
        "mle", "all", "guerrero".
    sp : int
        Seasonal periodicity of the data in integer form.
    lambda_ : float
        The Box-Cox lambda parameter that was solved for based on the supplied
        `method` and data provided in `fit`.


    Notes
    -----
    The Box-Cox transformation is defined as :math:`\frac{y^{\lambda}-1}{\lambda},
    \lambda \ne 0 \text{ or } ln(y), \lambda = 0`.

    Therefore, the input data must be positive. In some implementations, a positive
    constant is added to the series prior to applying the transformation. But
    that is not the case here.

    References
    ----------
    .. [1] Box, G. E. P. & Cox, D. R. (1964) An analysis of transformations,
       Journal of the Royal Statistical Society, Series B, 26, 211-252.
    .. [2] V.M. Guerrero, "Time-series analysis supported by Power
       Transformations ", Journal of Forecasting, vol. 12, pp. 37-48, 1993.

    Examples
    --------
    >>> from aeon.transformations.series._boxcox import BoxCoxTransformer
    >>> from aeon.datasets import load_airline
    >>> y = load_airline()
    >>> transformer = BoxCoxTransformer()
    >>> y_hat = transformer.fit_transform(y)
    """

    _tags = {
        "X_inner_type": "np.ndarray",
        "fit_is_empty": False,
        "capability:multivariate": False,
        "capability:inverse_transform": True,
    }

    def __init__(self, bounds=None, method="mle", sp=None):
        self.bounds = bounds
        self.method = method
        self.lambda_ = None
        self.sp = sp
        super().__init__(axis=1)

    def _fit(self, X, y=None):
        """
        Fit transformer to X and y.

        private _fit containing the core logic, called from fit

        Parameters
        ----------
        X : np.ndarray
            Time series to be transformed
        y : ignored argument for interface compatibility
            Additional data, e.g., labels for transformation

        Returns
        -------
        self: a fitted instance of the estimator
        """
        X = X.squeeze()
        if self.method == "guerrero":
            self.lambda_ = _guerrero(X, self.sp, self.bounds)
        else:
            self.lambda_ = _boxcox_normmax(X, bounds=self.bounds, method=self.method)

        return self

    def _transform(self, X, y=None):
        """Transform X and return a transformed version.

        private _transform containing the core logic, called from transform

        Parameters
        ----------
        X : np.ndarray
            Time series to be transformed
        y : ignored argument for interface compatibility
            Additional data, e.g., labels for transformation

        Returns
        -------
        Xt : 2D np.ndarray
            transformed version of X
        """
        X = X.squeeze()
        Xt = boxcox(X, self.lambda_)
        return Xt

    def _inverse_transform(self, X, y=None):
        """Inverse transform X and return an inverse transformed version.

        core logic

        Parameters
        ----------
        X : np.ndarray
            Time series to be transformed
        y : ignored argument for interface compatibility
            Additional data, e.g., labels for transformation

        Returns
        -------
        Xt : 2D np.ndarray
            inverse transformed version of X
        """
        Xt = inv_boxcox(X, self.lambda_)
        return Xt


def _make_boxcox_optimizer(bounds=None, brack=(-2.0, 2.0)):
    # bounds is None, use simple Brent optimisation
    if bounds is None:

        def optimizer(func, args):
            return optimize.brent(func, brack=brack, args=args)

    # otherwise use bounded Brent optimisation
    else:
        # input checks on bounds
        if not isinstance(bounds, tuple) or len(bounds) != 2:
            raise ValueError(
                f"`bounds` must be a tuple of length 2, but found: {bounds}"
            )

        def optimizer(func, args):
            return optimize.fminbound(func, bounds[0], bounds[1], args=args)

    return optimizer


def _boxcox_normmax(x, bounds=None, brack=(-2.0, 2.0), method="pearsonr"):
    optimizer = _make_boxcox_optimizer(bounds, brack)

    def _pearsonr(x):
        osm_uniform = _calc_uniform_order_statistic_medians(len(x))
        xvals = distributions.norm.ppf(osm_uniform)

        def _eval_pearsonr(lmbda, xvals, samps):
            y = _boxcox(samps, lmbda)
            yvals = np.sort(y)
            r, prob = stats.pearsonr(xvals, yvals)
            return 1 - r

        return optimizer(_eval_pearsonr, args=(xvals, x))

    def _mle(x):
        def _eval_mle(lmb, data):
            # function to minimize
            return -boxcox_llf(lmb, data)

        return optimizer(_eval_mle, args=(x,))

    def _all(x):
        maxlog = np.zeros(2, dtype=float)
        maxlog[0] = _pearsonr(x)
        maxlog[1] = _mle(x)
        return maxlog

    methods = {"pearsonr": _pearsonr, "mle": _mle, "all": _all}
    if method not in methods.keys():
        raise ValueError("Method %s not recognized." % method)

    optimfunc = methods[method]
    return optimfunc(x)


def _guerrero(x, sp, bounds=None):
    """Estimate lambda using the Guerrero method as described in [1]_.

    Parameters
    ----------
    x : ndarray
        1D time series.
    sp : integer
        Seasonal periodicity value. Must be an integer >= 2.
    bounds : {None, (float, float)}, optional
        Bounds on lambda to be used in minimization.

    Returns
    -------
    lambda : float
        Lambda value that minimizes the coefficient of variation of
        variances of the time series in different periods after
        Box-Cox transformation [Guerrero].

    References
    ----------
    .. [1] V.M. Guerrero, "Time-series analysis supported by Power
       Transformations ", Journal of Forecasting, vol. 12, pp. 37-48, 1993.
    """
    if sp is None or not is_int(sp) or sp < 2:
        raise ValueError(
            "Guerrero method requires an integer seasonal periodicity (sp) value >= 2."
        )

    x = np.asarray(x)
    if x.ndim != 1:
        raise ValueError("Data must be 1-dimensional.")

    num_obs = len(x)
    len_prefix = num_obs % sp

    x_trimmed = x[len_prefix:]
    x_mat = x_trimmed.reshape((-1, sp))
    x_mean = np.mean(x_mat, axis=1)

    # [Guerrero, Eq.(5)] uses an unbiased estimation for
    # the standard deviation
    x_std = np.std(x_mat, axis=1, ddof=1)

    def _eval_guerrero(lmb, x_std, x_mean):
        x_ratio = x_std / x_mean ** (1 - lmb)
        x_ratio_cv = variation(x_ratio)
        return x_ratio_cv

    optimizer = _make_boxcox_optimizer(bounds)
    return optimizer(_eval_guerrero, args=(x_std, x_mean))


def _boxcox(x, lmbda=None, bounds=None):
    r"""Return a dataset transformed by a Box-Cox power transformation.

    Parameters
    ----------
    x : ndarray
        Input array.  Must be positive 1-dimensional.  Must not be constant.
    lmbda : {None, scalar}, optional
        If `lmbda` is not None, do the transformation for that value.
        If `lmbda` is None, find the lambda that maximizes the log-likelihood
        function and return it as the second output argument.

    Returns
    -------
    boxcox : ndarray
        Box-Cox power transformed array.
    maxlog : float, optional
        If the `lmbda` parameter is None, the second returned argument is
        the lambda that maximizes the log-likelihood function.

    See Also
    --------
    probplot, boxcox_normplot, boxcox_normmax, boxcox_llf

    Notes
    -----
    The Box-Cox transform is given by::
        y = (x**lmbda - 1) / lmbda,  for lmbda > 0
            log(x),                  for lmbda = 0
    `boxcox` requires the input data to be positive.  Sometimes a Box-Cox
    transformation provides a shift parameter to achieve this; `boxcox` does
    not.  Such a shift parameter is equivalent to adding a positive constant to
    `x` before calling `boxcox`.
    The confidence limits returned when ``alpha`` is provided give the interval
    where:

    .. math::

        llf(\hat{\lambda}) - llf(\lambda) < \frac{1}{2}\chi^2(1 - \alpha, 1),
    with ``llf`` the log-likelihood function and :math:`\chi^2` the chi-squared
    function.

    References
    ----------
    G.E.P. Box and D.R. Cox, "An Analysis of Transformations", Journal of the
    Royal Statistical Society B, 26, 211-252 (1964).
    """
    x = np.asarray(x)
    if x.ndim != 1:
        raise ValueError("Data must be 1-dimensional.")

    if x.size == 0:
        return x

    if np.all(x == x[0]):
        raise ValueError("Data must not be constant.")

    if any(x <= 0):
        raise ValueError("Data must be positive.")

    if lmbda is not None:  # single transformation
        return special.boxcox(x, lmbda)

    # If lmbda=None, find the lmbda that maximizes the log-likelihood function.
    lmax = _boxcox_normmax(x, bounds=bounds, method="mle")
    y = _boxcox(x, lmax)

    return y, lmax
