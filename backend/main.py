"""Drift Guard backend — FastAPI.

Run from repo root:
    python -m uvicorn backend.main:app --reload

Dashboard: http://127.0.0.1:8000/   API docs: http://127.0.0.1:8000/docs
"""
import json
import logging
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.db import conn, init_db
from detector.drift_engine import compare, compare_outputs, confirmed
from shared.config import (
    ACTION_BY_SEVERITY, ALL_FEATURES, CATEGORICAL_FEATURES,
    CONSECUTIVE_BREACHES, NUMERIC_FEATURES, ROLLING_WINDOW,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("drift-guard")

BASELINE: pd.DataFrame | None = None
BASELINE_N = 10000
MODEL = None            # dummy fraud classifier ("the deployed model")
MODEL_COLS: list[str] = []
BASELINE_OUT: dict = {}   # {conf, acc, pred_fraud_rate, true_fraud_rate}
BASELINE_HISTS: dict = {}  # feature -> {kind, edges|labels, counts|shares}
_baseline_lock = threading.Lock()
HIST_BINS = 20


def _histograms(df: pd.DataFrame) -> dict:
    """Frozen-bin histograms for overlay charts. Numeric bins come from
    baseline quantiles so every batch is drawn on the same axis."""
    hists = {}
    for f in NUMERIC_FEATURES:
        edges = np.unique(np.percentile(df[f].dropna(), np.linspace(0, 100, HIST_BINS + 1)))
        counts, _ = np.histogram(df[f].dropna(), bins=edges)
        hists[f] = {"kind": "numeric", "edges": [round(float(e), 4) for e in edges],
                    "counts": [int(x) for x in counts], "n": int(len(df))}
    for f in CATEGORICAL_FEATURES:
        vc = df[f].astype(str).value_counts(normalize=True)
        hists[f] = {"kind": "categorical", "labels": list(vc.index),
                    "shares": [round(float(x), 4) for x in vc.values], "n": int(len(df))}
    return hists


def _ensure_baseline() -> pd.DataFrame:
    global BASELINE, MODEL, MODEL_COLS, BASELINE_OUT, BASELINE_HISTS
    if BASELINE is None:
        with _baseline_lock:
            if BASELINE is None:  # double-checked: threads may queue here
                from simulation.fraud_gen import get_batch
                from simulation.model import train
                BASELINE = get_batch(BASELINE_N, "baseline", seed=42)
                MODEL, MODEL_COLS, BASELINE_OUT = train(BASELINE)
                BASELINE_HISTS = _histograms(BASELINE)
                log.info("baseline loaded: %d rows, model acc=%.3f",
                         len(BASELINE), BASELINE_OUT["acc"])
    return BASELINE


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _ensure_baseline()
    log.info("drift-guard ready")
    yield


app = FastAPI(title="Drift Guard — Early Warning API", version="1.0.0", lifespan=lifespan)


class Ingest(BaseModel):
    transactions: list[dict] = Field(min_length=1)
    scenario: str = "live"


def _recent_severities(cur, k: int) -> list[str]:
    rows = cur.execute(
        "SELECT severity FROM drift_scores ORDER BY batch_id DESC LIMIT ?", (k,)).fetchall()
    return [r[0] for r in reversed(rows)]


def _store_and_respond(batch: pd.DataFrame, scenario: str) -> dict:
    baseline = _ensure_baseline()
    from simulation.model import score_batch
    try:
        r = compare(baseline, batch)
        bout = score_batch(MODEL, MODEL_COLS, batch)
        o = compare_outputs(BASELINE_OUT["conf"], bout["conf"])
    except ValueError as e:  # bad columns / empty features -> 400, not 500
        raise HTTPException(status_code=400, detail=str(e))
    with conn() as c:
        cur = c.cursor()
        cur.execute("INSERT INTO batches(n, scenario) VALUES(?,?)", (len(batch), scenario))
        bid = cur.lastrowid
        cur.execute("INSERT INTO drift_scores VALUES(?,?,?,?)",
                    (bid, r["psi_global"], r["severity"], r.get("top_feature", "")))
        for f, s in r.get("per_feature", {}).items():
            cur.execute("INSERT INTO feature_scores VALUES(?,?,?)", (bid, f, s["psi"]))
        cur.execute("INSERT INTO output_scores VALUES(?,?,?,?,?)",
                    (bid, bout["pred_fraud_rate"], bout["true_fraud_rate"],
                     bout["acc"], o["psi_conf"]))
        for f, h in _histograms(batch).items():
            if h["kind"] == "numeric":
                # re-bin batch on BASELINE edges so overlay shares one axis
                edges = np.array(BASELINE_HISTS[f]["edges"])
                counts, _ = np.histogram(batch[f].dropna(), bins=edges)
                cur.execute("INSERT INTO histograms VALUES(?,?,?,?,?,?)",
                            (bid, f, "numeric", json.dumps([float(e) for e in edges]),
                             json.dumps([int(x) for x in counts]), len(batch)))
            else:
                order = BASELINE_HISTS[f]["labels"]
                vc = batch[f].astype(str).value_counts(normalize=True)
                cur.execute("INSERT INTO histograms VALUES(?,?,?,?,?,?)",
                            (bid, f, "categorical", json.dumps(order),
                             json.dumps([round(float(vc.get(k, 0.0)), 4) for k in order]),
                             len(batch)))
        sev = _recent_severities(cur, CONSECUTIVE_BREACHES)
        hist = cur.execute(
            "SELECT psi_global FROM drift_scores ORDER BY batch_id DESC LIMIT ?",
            (ROLLING_WINDOW,)).fetchall()
    is_confirmed = confirmed(sev)
    rolling = round(sum(h[0] for h in hist) / len(hist), 4) if hist else 0.0
    action = ACTION_BY_SEVERITY.get(r["severity"], "log")
    outputs = {"pred_fraud_rate": bout["pred_fraud_rate"],
               "true_fraud_rate": bout["true_fraud_rate"], "acc": bout["acc"],
               "mean_conf": bout["mean_conf"], **o,
               "acc_drop": round(BASELINE_OUT["acc"] - bout["acc"], 4)
               if bout["acc"] is not None else None}
    if r["severity"] == "severe":
        Path("retrain_trigger.json").write_text(json.dumps(
            {"batch_id": bid, "top_feature": r.get("top_feature"),
             "psi_global": r["psi_global"], "confirmed": is_confirmed,
             "acc": bout["acc"]}))
        log.warning("SEVERE drift batch=%d top=%s acc=%s confirmed=%s",
                    bid, r.get("top_feature"), bout["acc"], is_confirmed)
    else:
        log.info("batch=%d scenario=%s psi=%s severity=%s acc=%s",
                 bid, scenario, r["psi_global"], r["severity"], bout["acc"])
    return {**r, "action": action, "batch_id": bid, "outputs": outputs,
            "rolling_psi": rolling, "alert_confirmed": is_confirmed}


@app.get("/health")
def health():
    with conn() as c:
        n = c.execute("SELECT COUNT(*) FROM batches").fetchone()[0]
    return {"status": "ok", "version": "1.0.0",
            "baseline_rows": len(BASELINE) if BASELINE is not None else 0,
            "batches": n}


@app.post("/baseline/load")
def load_baseline(n: int = 10000):
    if n < 1000:
        raise HTTPException(status_code=400, detail="n must be >= 1000 for a stable baseline")
    global BASELINE, BASELINE_N, MODEL, MODEL_COLS, BASELINE_OUT, BASELINE_HISTS
    from simulation.fraud_gen import get_batch
    from simulation.model import train
    with _baseline_lock:
        BASELINE_N = n
        BASELINE = get_batch(n, "baseline", seed=42)
        MODEL, MODEL_COLS, BASELINE_OUT = train(BASELINE)
        BASELINE_HISTS = _histograms(BASELINE)
    return {"rows": len(BASELINE), "status": "baseline-set",
            "model_acc": round(BASELINE_OUT["acc"], 4)}


@app.post("/ingest", status_code=201)
def ingest(body: Ingest):
    return _store_and_respond(pd.DataFrame(body.transactions), body.scenario)


@app.post("/simulate/{scenario}", status_code=201)
def simulate(scenario: str, n: int = 800, seed: int | None = None):
    """One-click demo feed: generate a synthetic batch and ingest it."""
    if scenario not in ("normal", "gradual", "spike"):
        raise HTTPException(status_code=400, detail="scenario must be normal|gradual|spike")
    if n < 1:
        raise HTTPException(status_code=400, detail="n must be >= 1")
    from simulation.fraud_gen import get_batch
    return _store_and_respond(get_batch(n, scenario, seed), scenario)


@app.post("/reset")
def reset():
    """Clear history for a fresh demo. Baseline + model are kept."""
    _ensure_baseline()
    with conn() as c:
        for t in ("histograms", "output_scores", "feature_scores", "drift_scores", "batches"):
            c.execute(f"DELETE FROM {t}")
        c.execute("DELETE FROM sqlite_sequence WHERE name='batches'")
    p = Path("retrain_trigger.json")
    if p.exists():
        p.unlink()
    log.info("demo reset")
    return {"status": "reset", "baseline_rows": len(BASELINE)}


@app.get("/scores")
def scores(limit: int = 50):
    with conn() as c:
        rows = c.execute(
            "SELECT b.id, b.ts, b.scenario, d.psi_global, d.severity, d.top_feature "
            "FROM batches b JOIN drift_scores d ON d.batch_id=b.id "
            "ORDER BY b.id DESC LIMIT ?", (limit,)).fetchall()
        ids = [r[0] for r in rows]
        feats = c.execute(
            f"SELECT batch_id, feature, psi FROM feature_scores WHERE batch_id IN "
            f"({','.join('?' * len(ids))})", ids).fetchall() if ids else []
        outs = c.execute(
            f"SELECT batch_id, pred_fraud_rate, true_fraud_rate, acc, psi_conf "
            f"FROM output_scores WHERE batch_id IN "
            f"({','.join('?' * len(ids))})", ids).fetchall() if ids else []
    out = [{"batch_id": r[0], "ts": r[1], "scenario": r[2], "psi": r[3],
            "severity": r[4], "top": r[5]} for r in reversed(rows)]
    for i, o in enumerate(out):  # confirmed = last `need` batches ending here all breached
        o["confirmed"] = confirmed([x["severity"] for x in out[:i + 1]])
    return {"baseline_rows": len(BASELINE) if BASELINE is not None else 0,
            "baseline_acc": round(BASELINE_OUT.get("acc", 0.0), 4) if BASELINE_OUT else 0.0,
            "scores": out,
            "features": [{"batch_id": f[0], "feature": f[1], "psi": f[2]} for f in feats],
            "outputs": [{"batch_id": x[0], "pred_fraud_rate": x[1], "true_fraud_rate": x[2],
                         "acc": x[3], "psi_conf": x[4]} for x in outs]}


@app.get("/alerts")
def alerts(limit: int = 20):
    """Confirmed moderate/severe breaches, newest first — the paging list."""
    with conn() as c:
        rows = c.execute(
            "SELECT b.id, b.ts, b.scenario, d.psi_global, d.severity, d.top_feature "
            "FROM batches b JOIN drift_scores d ON d.batch_id=b.id "
            "WHERE d.severity IN ('moderate','severe') "
            "ORDER BY b.id DESC LIMIT ?", (limit,)).fetchall()
    return {"alerts": [{"batch_id": r[0], "ts": r[1], "scenario": r[2], "psi": r[3],
                        "severity": r[4], "top": r[5]} for r in rows]}


@app.get("/distributions")
def distributions(feature: str = "amount"):
    """Mugshot vs lineup: baseline vs latest-batch distribution for one feature."""
    if feature not in ALL_FEATURES:
        raise HTTPException(status_code=400, detail=f"feature must be one of {ALL_FEATURES}")
    _ensure_baseline()
    base = BASELINE_HISTS[feature]
    with conn() as c:
        bid = c.execute("SELECT MAX(id) FROM batches").fetchone()[0]
        row = c.execute(
            "SELECT kind, edges_json, counts_json, n FROM histograms "
            "WHERE batch_id=? AND feature=?", (bid, feature)).fetchone() if bid else None
    if row is None:
        latest = None
    else:
        kind, edges, counts, n = row[0], json.loads(row[1]), json.loads(row[2]), row[3]
        latest = {"kind": kind, "axis": edges, "values": counts, "n": n}
    if base["kind"] == "numeric":
        axis, bvals = base["edges"], base["counts"]
    else:
        axis, bvals = base["labels"], base["shares"]
    return {"feature": feature, "kind": base["kind"], "axis": axis,
            "baseline": {"values": bvals, "n": base["n"]},
            "latest": latest, "latest_batch_id": bid}


app.mount("/", StaticFiles(directory="frontend", html=True), name="web")
