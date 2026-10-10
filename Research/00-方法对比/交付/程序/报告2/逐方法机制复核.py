"""Check six method criteria on two abnormal/control pairs, without run().

Outputs stay beside this script. Conditional calculations explain the archived
estimates; they do not replace estimates, convergence states, or frequencies.
"""
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, snapshot_path
DATA_DIR = RESULT / "报告2" / "数据"
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

import numpy as np
from scipy.optimize import brentq, minimize_scalar
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
INPUTS = {
    "high": ("W(2,100,500)", 15, 36),
    "high_control": ("W(2,100,500)", 15, 35),
    "low": ("W(5,100,500)", 7, 11),
    "low_control": ("W(5,100,500)", 7, 10),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cov(a, b):
    return float(np.mean((a - a.mean()) * (b - b.mean())))


def shape_profile(x, gamma, j2=1.0):
    """Fixed-location shape score; j2=1 gives ordinary conditional MLE."""
    t = np.log(x - gamma)
    z = t - t.mean()

    def score(beta):
        w = np.exp(beta * (z - z.max()))
        w /= w.sum()
        return j2 / beta - float(w @ z)

    upper = 2.0
    while score(upper) > 0:
        upper *= 2
    beta = brentq(score, 1e-8, upper, xtol=1e-11, rtol=2e-14)
    log_eta = t.mean() + (logsumexp(beta * z) - np.log(len(x))) / beta
    ll = len(x) * (np.log(beta) - t.mean() - logsumexp(beta*z) + np.log(len(x)) - 1)
    w = np.exp(beta * (z - z.max()))
    w /= w.sum()
    grad = len(x) * (beta * float(w @ (1/(x-gamma))) - (beta-1)*np.mean(1/(x-gamma)))
    return dict(beta=float(beta), eta=float(np.exp(log_eta)), ll=float(ll),
                location_score=float(grad), shape_score=float(score(beta)))


def regression(x, gamma, z, method):
    y = np.log(x-gamma)
    c, vy, vz = cov(y, z), cov(y, y), cov(z, z)
    r2 = c*c/(vy*vz)
    beta = vz/c if method == "LSE" else c/vy
    eta = np.exp(y.mean()-z.mean()/beta)
    return dict(beta=float(beta), eta=float(eta), r2=float(r2),
                relative_residual=float(1-r2),
                fisher_ratio=float((len(x)-2)/(len(x)-1)/(1-r2)))


def mdm_profile(x, gamma):
    p = (np.arange(1, len(x)+1)-.3)/(len(x)+.4)
    u = -np.log1p(-p)

    def sigma(beta):
        return float(np.std((x-gamma)*u**(-1/beta), ddof=1))

    fit = minimize_scalar(sigma, bounds=(.1, 15), method="bounded")
    w = u**(-1/fit.x)
    eta_i = (x-gamma)*w
    grad = float(-np.cov(eta_i, w, ddof=1)[0, 1]/fit.fun)
    bound = float(np.std(w, ddof=1))
    assert abs(grad) <= bound+1e-10
    step = min(x[0]*1e-5, (x[0]-gamma)*.25)
    if gamma > step:
        finite_grad = (mdm_sigma(x, gamma+step, u)-mdm_sigma(x, gamma-step, u))/(2*step)
    else:
        finite_grad = (mdm_sigma(x, gamma+step, u)-fit.fun)/step
    return dict(beta=float(fit.x), eta=float(np.mean(eta_i)), sigma=float(fit.fun),
                gradient=grad, gradient_bound=bound, finite_gradient=float(finite_grad))


def mdm_sigma(x, gamma, u):
    return float(minimize_scalar(lambda b: np.std((x-gamma)*u**(-1/b), ddof=1),
                                bounds=(.1, 15), method="bounded").fun)


def wmle_profile(x, gamma, weights):
    n = len(x)
    j1, j2 = weights.get_weight_j1(n), weights.get_weight_j2(n)
    profile = shape_profile(x, gamma, j2)
    beta = profile["beta"]
    t = np.log(x-gamma)
    # Center before powers to avoid overflow; the ratio retains one distance.
    z = t-t.mean()
    log_ratio = t.mean()+logsumexp(beta*z)-logsumexp((beta-1)*z)
    product = float(np.mean(1/(x-gamma))*np.exp(log_ratio))
    j3 = float(weights.get_weight_j3(n, beta))
    return dict(beta=beta, eta=float(profile["eta"]*j1**(-1/beta)),
                t1=profile["shape_score"], t2=float(product-j3),
                inverse_distance_product=product, j1=float(j1), j2=float(j2), j3=j3)
