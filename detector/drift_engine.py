"""Drift engine: compare one batch against the baseline.

Global score = MAX per-feature PSI (a single rotting feature must not be
averaged away by healthy ones). KS p-values get a Bonferroni correction
because we run one test per numeric feature — without it, 5 features at
alpha=0.05 would false-alarm ~23% of the time on pure noise.
"""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from detector.metrics import psi, psi_categorical, ks
from shared.config import (
    NUMERIC_FEATURES, CATEGORICAL_FEATURES, ALL_FEATURES,
    PSI_NONE, PSI_MILD, PSI_MODERATE, ALPHA, BATCH_MIN_N,
)

ALERT_SEVERITIES = ("moderate", "severe")


def severity_of(psi_val: float) -> str:
    if psi_val < PSI_NONE:
        return "none"
    if psi_val < PSI_MILD:
        return "mild"
    if psi_val < PSI_MODERATE:
        return "moderate"
    return "severe"


def _require_columns(df: pd.DataFrame, name: str) -> None:
    missing = [c for c in ALL_FEATURES if c not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing columns: {missing} "
                         f"(required: {ALL_FEATURES})")


def compare(baseline: pd.DataFrame, batch: pd.DataFrame) -> dict:
    """Return {psi_global, severity, top_feature, per_feature}.

    Raises ValueError on missing columns or empty (all-NaN) features.
    Batches smaller than BATCH_MIN_N return severity 'no-decision'.
    """
    _require_columns(baseline, "baseline")
    _require_columns(batch, "batch")
    if len(batch) < BATCH_MIN_N:
        return {"psi_global": 0.0, "severity": "no-decision",
                "reason": f"n={len(batch)} < {BATCH_MIN_N}", "per_feature": {}}
    m = len(NUMERIC_FEATURES)  # Bonferroni denominator
    per = {}
    for f in NUMERIC_FEATURES:
        v = psi(baseline[f], batch[f])
        d, p = ks(baseline[f], batch[f])
        per[f] = {"psi": round(v, 4), "ks_D": round(d, 4),
                  "ks_p": round(p, 5), "ks_p_adj": round(min(p * m, 1.0), 5),
                  "ks_sig": bool(min(p * m, 1.0) < ALPHA)}
    for f in CATEGORICAL_FEATURES:
        v = psi_categorical(baseline[f].astype(str), batch[f].astype(str))
        per[f] = {"psi": round(v, 4), "ks_D": None, "ks_p": None,
                  "ks_p_adj": None, "ks_sig": None}
    g = round(float(max(x["psi"] for x in per.values())), 4)
    top = max(per, key=lambda k: per[k]["psi"])
    return {"psi_global": g, "severity": severity_of(g),
            "top_feature": top, "per_feature": per}


def confirmed(severities: list[str], need: int = 2) -> bool:
    """True when the last `need` batches all breached (moderate/severe).

    This is the 'doesn't cry wolf' rule: a lone spike is logged, a repeated
    breach pages a human.
    """
    tail = severities[-need:]
    return len(tail) == need and all(s in ALERT_SEVERITIES for s in tail)


def compare_outputs(base_conf: pd.Series, batch_conf: pd.Series) -> dict:
    """Output-side drift: does the model's confidence distribution still look
    like deployment day? Returns {psi_conf, ks_D, ks_p}."""
    v = psi(base_conf, batch_conf)
    d, p = ks(base_conf, batch_conf)
    return {"psi_conf": round(float(v), 4), "ks_D": round(float(d), 4),
            "ks_p": round(float(p), 5)}
