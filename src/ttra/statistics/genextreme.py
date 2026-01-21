import numpy as np
from scipy.stats import genextreme
from scipy.optimize import minimize


def guess_params(x) -> tuple:
    shape, loc, scale = genextreme.fit(x)
    return shape, loc, scale


def pdf(x, shape, loc, scale):
    return genextreme.pdf(x, shape, loc=loc, scale=scale)


def ppf(x, shape, loc, scale):
    return genextreme.ppf(x, shape, loc=loc, scale=scale)


def nll(params, data):
    shape, loc, scale = params
    if scale <= 0:
        return 1e10
    return -np.sum(genextreme.logpdf(data, shape, loc=loc, scale=scale))


def fit(x) -> tuple:
    """
    GEV with constraints for temperature.
    Ref for shape constraints: doi:10.1029/2006JD008091
    """
    init_params = guess_params(x)

    bounds = [(-0.2, 0.2), (None, None), (0.01, None)]

    res = minimize(nll, init_params, args=(x,), bounds=bounds, method='L-BFGS-B')
    if res.success:
        shape, loc, scale = res.x
        return shape, loc, scale
    else:
        raise RuntimeError("GEV fit did not converge")