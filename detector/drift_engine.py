"""Role 2 — drift_engine: batch vs baseline -> global + per-feature scores."""
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from detector.metrics import psi, psi_categorical, ks
from shared.config import NUMERIC_FEATURES, CATEGORICAL_FEATURES, PSI_NONE, PSI_MILD, BATCH_MIN_N


def severity_of(psi_val: float) -> str:
    if psi_val < PSI_NONE:
        return "none"
    if psi_val < PSI_MILD:
        return "mild"
    if psi_val < 0.5:
        return "moderate"
    return "severe"


def compare(baseline: pd.DataFrame, batch: pd.DataFrame) -> dict:
    if len(batch) < BATCH_MIN_N:
        return {"psi_global": 0.0, "severity": "no-decision",
                "reason": f"n={len(batch)} < {BATCH_MIN_N}", "per_feature": {}}
    per = {}
    for f in NUMERIC_FEATURES:
        v = psi(baseline[f], batch[f])
        d, p = ks(baseline[f], batch[f])
        per[f] = {"psi": round(v, 4), "ks_D": round(d, 4), "ks_p": round(p, 5)}
    for f in CATEGORICAL_FEATURES:
        v = psi_categorical(baseline[f].astype(str), batch[f].astype(str))
        per[f] = {"psi": round(v, 4), "ks_D": None, "ks_p": None}
    g = round(float(max(x["psi"] for x in per.values())), 4)
    top = max(per, key=lambda k: per[k]["psi"])
    return {"psi_global": g, "severity": severity_of(g), "top_feature": top, "per_feature": per}
