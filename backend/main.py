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

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.db import conn, init_db
from detector.drift_engine import compare, confirmed
from shared.config import (
    ACTION_BY_SEVERITY, CONSECUTIVE_BREACHES, ROLLING_WINDOW,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("drift-guard")

BASELINE: pd.DataFrame | None = None
BASELINE_N = 10000
_baseline_lock = threading.Lock()


def _ensure_baseline() -> pd.DataFrame:
    global BASELINE
    if BASELINE is None:
        with _baseline_lock:
            if BASELINE is None:  # double-checked: threads may queue here
                from simulation.fraud_gen import get_batch
                BASELINE = get_batch(BASELINE_N, "baseline", seed=42)
                log.info("baseline loaded: %d rows", len(BASELINE))
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
    try:
        r = compare(baseline, batch)
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
        sev = _recent_severities(cur, CONSECUTIVE_BREACHES)
        hist = cur.execute(
            "SELECT psi_global FROM drift_scores ORDER BY batch_id DESC LIMIT ?",
            (ROLLING_WINDOW,)).fetchall()
    is_confirmed = confirmed(sev)
    rolling = round(sum(h[0] for h in hist) / len(hist), 4) if hist else 0.0
    action = ACTION_BY_SEVERITY.get(r["severity"], "log")
    if r["severity"] == "severe":
        Path("retrain_trigger.json").write_text(json.dumps(
            {"batch_id": bid, "top_feature": r.get("top_feature"),
             "psi_global": r["psi_global"], "confirmed": is_confirmed}))
        log.warning("SEVERE drift batch=%d top=%s confirmed=%s", bid, r.get("top_feature"), is_confirmed)
    else:
        log.info("batch=%d scenario=%s psi=%s severity=%s", bid, scenario, r["psi_global"], r["severity"])
    return {**r, "action": action, "batch_id": bid,
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
    global BASELINE, BASELINE_N
    from simulation.fraud_gen import get_batch
    with _baseline_lock:
        BASELINE_N = n
        BASELINE = get_batch(n, "baseline", seed=42)
    return {"rows": len(BASELINE), "status": "baseline-set"}


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
    """Clear history for a fresh demo. Baseline is kept."""
    _ensure_baseline()
    with conn() as c:
        c.execute("DELETE FROM feature_scores")
        c.execute("DELETE FROM drift_scores")
        c.execute("DELETE FROM batches")
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
    out = [{"batch_id": r[0], "ts": r[1], "scenario": r[2], "psi": r[3],
            "severity": r[4], "top": r[5]} for r in reversed(rows)]
    for i, o in enumerate(out):  # confirmed = last `need` batches ending here all breached
        o["confirmed"] = confirmed([x["severity"] for x in out[:i + 1]])
    return {"baseline_rows": len(BASELINE) if BASELINE is not None else 0,
            "scores": out,
            "features": [{"batch_id": f[0], "feature": f[1], "psi": f[2]} for f in feats]}


app.mount("/", StaticFiles(directory="frontend", html=True), name="web")
