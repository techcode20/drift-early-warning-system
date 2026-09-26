"""Role 3 — backend: FastAPI. Run: uvicorn backend.main:app --reload"""
import sys
from pathlib import Path
import pandas as pd
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from detector.drift_engine import compare
from backend.db import conn

app = FastAPI(title="Drift Early Warning")
BASELINE: pd.DataFrame | None = None


class Ingest(BaseModel):
    transactions: list[dict]
    scenario: str = "live"


@app.post("/baseline/load")
def load_baseline(n: int = 10000):
    global BASELINE
    from simulation.fraud_gen import get_batch
    BASELINE = get_batch(n, "baseline", seed=42)
    return {"rows": len(BASELINE), "status": "baseline-set"}


def _store_and_respond(batch: pd.DataFrame, scenario: str) -> dict:
    r = compare(BASELINE, batch)
    c = conn()
    cur = c.cursor()
    cur.execute("INSERT INTO batches(n, scenario) VALUES(?,?)", (len(batch), scenario))
    bid = cur.lastrowid
    cur.execute("INSERT INTO drift_scores VALUES(?,?,?,?)",
                (bid, r["psi_global"], r["severity"], r.get("top_feature", "")))
    for f, s in r.get("per_feature", {}).items():
        cur.execute("INSERT INTO feature_scores VALUES(?,?,?)", (bid, f, s["psi"]))
    # auto-response
    action = {"none": "log", "mild": "log", "moderate": "alert-human",
              "severe": "trigger-retrain", "no-decision": "wait"}.get(r["severity"], "log")
    if r["severity"] == "severe":
        Path("retrain_trigger.json").write_text(f'{{"batch_id": {bid}, "top_feature": "{r.get("top_feature")}"}}')
    c.commit()
    c.close()
    return {**r, "action": action, "batch_id": bid}


@app.post("/ingest")
def ingest(body: Ingest):
    if BASELINE is None:
        return {"error": "call POST /baseline/load first"}
    return _store_and_respond(pd.DataFrame(body.transactions), body.scenario)


@app.post("/simulate/{scenario}")
def simulate(scenario: str, n: int = 800, seed: int | None = None):
    """One-click demo feed: generate a synthetic batch and ingest it."""
    if BASELINE is None:
        return {"error": "call POST /baseline/load first"}
    if scenario not in ("normal", "gradual", "spike"):
        return {"error": "scenario must be normal|gradual|spike"}
    from simulation.fraud_gen import get_batch
    return _store_and_respond(get_batch(n, scenario, seed), scenario)


@app.get("/scores")
def scores(limit: int = 50):
    c = conn()
    rows = c.execute(
        "SELECT b.id, b.ts, d.psi_global, d.severity, d.top_feature FROM batches b "
        "JOIN drift_scores d ON d.batch_id=b.id ORDER BY b.id DESC LIMIT ?", (limit,)).fetchall()
    feats = c.execute("SELECT batch_id, feature, psi FROM feature_scores").fetchall()
    c.close()
    return {"scores": [{"batch_id": r[0], "ts": r[1], "psi": r[2], "severity": r[3], "top": r[4]} for r in reversed(rows)],
            "features": [{"batch_id": f[0], "feature": f[1], "psi": f[2]} for f in feats]}


app.mount("/", StaticFiles(directory="frontend", html=True), name="web")
