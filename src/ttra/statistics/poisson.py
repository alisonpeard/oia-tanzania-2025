import numpy as np
from scipy.stats import poisson


def nll(params, y, X):
    beta0, beta1 = params
    lambda_ = np.exp(beta0 + beta1 * X)
    return -np.sum(poisson.logpmf(y, lambda_))


def expected_value(t, params):
    beta0, beta1 = params
    return np.exp(beta0 + beta1 * t)