"""Role 2 — detector: PSI / KS / KL. Pure functions, no DB, no API."""
import numpy as np
import pandas as pd
from scipy import stats

EPS = 1e-6


def _binned_pct(expected: pd.Series, actual: pd.Series, bins: int = 10):
    """Quantile bins from baseline, reused for batch. Returns (e%, a%)."""
    quantiles = np.linspace(0, 100, bins + 1)
    edges = np.unique(np.percentile(expected.dropna(), quantiles))
    if len(edges) < 3:
        edges = np.histogram_bin_edges(expected.dropna(), bins=bins)
    e_counts, _ = np.histogram(expected.dropna(), bins=edges)
    a_counts, _ = np.histogram(actual.dropna(), bins=edges)
    e_pct = e_counts / max(e_counts.sum(), 1)
    a_pct = a_counts / max(a_counts.sum(), 1)
    return np.clip(e_pct, EPS, 1), np.clip(a_pct, EPS, 1)


def psi(expected: pd.Series, actual: pd.Series, bins: int = 10) -> float:
    e, a = _binned_pct(expected, actual, bins)
    return float(np.sum((a - e) * np.log(a / e)))


def psi_categorical(expected: pd.Series, actual: pd.Series) -> float:
    cats = pd.unique(pd.concat([expected, actual]).dropna())
    e = np.array([(expected == c).mean() for c in cats])
    a = np.array([(actual == c).mean() for c in cats])
    e = np.clip(e, EPS, 1)
    a = np.clip(a, EPS, 1)
    return float(np.sum((a - e) * np.log(a / e)))


def ks(expected: pd.Series, actual: pd.Series):
    """Returns (D, p_value)."""
    r = stats.ks_2samp(expected.dropna(), actual.dropna())
    return float(r.statistic), float(r.pvalue)


def kl(expected: pd.Series, actual: pd.Series, bins: int = 10) -> float:
    e, a = _binned_pct(expected, actual, bins)
    return float(stats.entropy(a, e))
