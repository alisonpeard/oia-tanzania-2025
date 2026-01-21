import numpy as np
from scipy.stats import genpareto


def guess_params(x) -> tuple:
    init_params = genpareto.fit(x, floc=0)
    scale_init = init_params[2]
    shape_init = init_params[0]
    return scale_init, shape_init


def pmf(k, scale, shape):
    """
    Discrete Generalized Pareto Distribution PMF
    k: integer values (0, 1, 2, ...)
    scale: scale parameter (σ)
    shape: shape parameter (ξ)

    From https://arxiv.org/pdf/1707.05033
    """
    if shape == 0:
        # top of page 4
        p = 1 - np.exp(-1/scale)
        return p * np.exp(-k/scale)
    else:
        # Eq. (4)
        k_lower = 1 + shape * k / scale
        k1_lower = 1 + shape * (k + 1) / scale
        if k_lower <= 0 or k1_lower <= 0:
            return 0.0
        
        gpd_k = (1 + shape * k / scale)**(-1/shape)
        gpd_k1 = (1 + shape * (k + 1) / scale)**(-1/shape)
        return gpd_k - gpd_k1


def survival(k, scale, shape):
    """Survival function for D-GPD. This is the same 
    as the GPD."""
    if shape == 0:
        return np.exp(-k/scale)
    else:
        return (1 + shape * k / scale)**(-1/shape)


def quantile(p, scale, shape):
    """
    Quantile function for D-GPD (return level)
    p: exceedance probability (e.g., 1/return_period)
    """
    if shape == 0:
        x = -scale * np.log(p)
    else:
        x = (scale / shape) * (p**(-shape) - 1)
    return np.floor(x) # only floor if needd


def nll(params, data):
    """Negative log-likelihood for D-GPD"""
    scale, shape = params
    
    if scale <= 0:
        return np.inf
    
    log_probs = []
    for k in data:
        pmf_val = pmf(k, scale, shape)
        if pmf_val <= 0:
            return np.inf
        log_probs.append(np.log(pmf_val))
    
    return -np.sum(log_probs)