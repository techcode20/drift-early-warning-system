"""Statistical distance measures for drift detection.

All functions are pure (no DB, no API) and compare a *baseline* distribution
against a *batch* distribution:

- PSI  — binned divergence; the primary drift score (industry standard bands).
- KS   — Kolmogorov-Smirnov D + p-value; good for sudden shifts in numerics.
- KL   — Kullback-Leibler divergence; supplementary, same binning as PSI.

Convention: baseline defines the bins (quantiles). Reusing the same bins for
every batch is what makes scores comparable over time.
"""
import numpy as np
import pandas as pd
from scipy import stats

EPS = 1e-6  # floor so log-ratios never divide by zero


def _clean(s: pd.Series) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce") if s.dtype == object else s
    return s.dropna()


def _binned_pct(expected: pd.Series, actual: pd.Series, bins: int = 10):
    """Quantile bins from baseline, reused for batch. Returns (e%, a%)."""
    exp = _clean(expected)
    act = _clean(actual)
    if exp.empty or act.empty:
        raise ValueError("empty series after dropping NaNs — nothing to compare")
    quantiles = np.linspace(0, 100, bins + 1)
    edges = np.unique(np.percentile(exp, quantiles))
    if len(edges) < 3:  # near-constant baseline: fall back to equal-width bins
        edges = np.histogram_bin_edges(exp, bins=bins)
        if len(np.unique(edges)) < 3:
            return np.array([1.0]), np.array([1.0])  # both constant: identical
    e_counts, _ = np.histogram(exp, bins=edges)
    a_counts, _ = np.histogram(act, bins=edges)
    e_pct = np.clip(e_counts / max(e_counts.sum(), 1), EPS, 1)
    a_pct = np.clip(a_counts / max(a_counts.sum(), 1), EPS, 1)
    return e_pct, a_pct


def psi(expected: pd.Series, actual: pd.Series, bins: int = 10) -> float:
    """Population Stability Index. ~0 = identical, >0.25 = large shift."""
    e, a = _binned_pct(expected, actual, bins)
    return float(np.sum((a - e) * np.log(a / e)))


def psi_categorical(expected: pd.Series, actual: pd.Series) -> float:
    """PSI over category shares (no binning needed)."""
    exp = expected.dropna().astype(str)
    act = actual.dropna().astype(str)
    if exp.empty or act.empty:
        raise ValueError("empty series after dropping NaNs — nothing to compare")
    cats = pd.unique(pd.concat([exp, act]))
    e = np.clip(np.array([(exp == c).mean() for c in cats]), EPS, 1)
    a = np.clip(np.array([(act == c).mean() for c in cats]), EPS, 1)
    return float(np.sum((a - e) * np.log(a / e)))


def ks(expected: pd.Series, actual: pd.Series):
    """Kolmogorov-Smirnov test. Returns (D, p_value)."""
    exp, act = _clean(expected), _clean(actual)
    if exp.empty or act.empty:
        raise ValueError("empty series after dropping NaNs — nothing to compare")
    r = stats.ks_2samp(exp, act)
    return float(r.statistic), float(r.pvalue)


def kl(expected: pd.Series, actual: pd.Series, bins: int = 10) -> float:
    """KL divergence P(batch || baseline) on the PSI binning."""
    e, a = _binned_pct(expected, actual, bins)
    return float(stats.entropy(a, e))
