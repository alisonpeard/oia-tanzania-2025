import numpy as np
from scipy.stats import binom
from scipy.special import expit


def nll(params, y, X, n=365):
    beta0, beta1 = params
    p = expit(beta0 + beta1 * X)
    return -np.sum(binom.logpmf(y, n, p))


def expected_value(t, params, n=365):
    beta0, beta1 = params
    p = expit(beta0 + beta1 * t)
    return n * p