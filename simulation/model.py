"""Role 1 — dummy fraud model.

A plain LogisticRegression trained on baseline labels. It stands in for "the
deployed model": good on the world it trained on, blind when fraudsters
change tactics (spike mode). Exposes the *output* side of drift — prediction
rates, confidence, and accuracy — which input-only monitoring misses.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from simulation.fraud_gen import LABEL_COL

MODEL_FEATURES = ["amount", "hour", "location", "merchant", "device_age"]


def featurize(df: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame({
        "log_amount": np.log1p(df["amount"].astype(float)),
        "hour": df["hour"].astype(float),
        "log_device": np.log1p(df["device_age"].astype(float)),
    })
    x = pd.concat([x, pd.get_dummies(df["location"].astype(str), prefix="loc"),
                   pd.get_dummies(df["merchant"].astype(str), prefix="m")], axis=1)
    return x


def train(df: pd.DataFrame):
    """Fit on baseline. Returns (model, columns, baseline_outputs)."""
    if LABEL_COL not in df.columns:
        raise ValueError("baseline has no labels — generate with with_label=True")
    X = featurize(df).astype(float)
    y = df[LABEL_COL].astype(int)
    model = LogisticRegression(max_iter=500)
    model.fit(X, y)
    proba = model.predict_proba(X)[:, 1]
    return model, list(X.columns), {
        "conf": pd.Series(proba),
        "acc": float(model.score(X, y)),
        "pred_fraud_rate": float((proba >= 0.5).mean()),
        "true_fraud_rate": float(y.mean()),
    }


def score_batch(model, columns: list[str], df: pd.DataFrame) -> dict:
    """Predict one batch. Accuracy is None when labels are absent (real world:
    labels arrive late — the dashboard shows input drift first, accuracy later)."""
    X = featurize(df).astype(float).reindex(columns=columns, fill_value=0.0)
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    out = {"conf": pd.Series(proba),
           "pred_fraud_rate": round(float(pred.mean()), 4),
           "mean_conf": round(float(np.maximum(proba, 1 - proba).mean()), 4)}
    if LABEL_COL in df.columns:
        y = df[LABEL_COL].astype(int)
        out["true_fraud_rate"] = round(float(y.mean()), 4)
        out["acc"] = round(float((pred == y).mean()), 4)
    else:
        out["true_fraud_rate"] = None
        out["acc"] = None
    return out
