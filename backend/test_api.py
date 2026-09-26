"""API tests. Each test gets a fresh temp DB via DRIFT_DB (see backend/db.py)."""
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DRIFT_DB"] = _tmp.name

import backend.main as main  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(main.app) as c:
        c.post("/reset")
        yield c


def test_health(client):
    r = client.get("/health").json()
    assert r["status"] == "ok" and r["baseline_rows"] == 10000


def test_baseline_auto_loaded_no_docs_detour(client):
    # no explicit /baseline/load needed: lifespan + _ensure_baseline cover it
    assert client.get("/health").json()["baseline_rows"] > 0


def test_simulate_all_scenarios(client):
    n = client.post("/simulate/normal", params={"n": 800, "seed": 7}).json()
    g = client.post("/simulate/gradual", params={"n": 800, "seed": 7}).json()
    s = client.post("/simulate/spike", params={"n": 800, "seed": 7}).json()
    assert n["severity"] == "none" and n["action"] == "log"
    assert g["top_feature"] == "amount" and g["psi_global"] > 0.1
    assert s["severity"] == "severe" and s["top_feature"] == "location"
    assert s["action"] == "trigger-retrain"
    assert {"rolling_psi", "alert_confirmed", "batch_id"} <= set(s)


def test_second_breach_confirms(client):
    client.post("/simulate/spike", params={"n": 800, "seed": 7})
    second = client.post("/simulate/spike", params={"n": 800, "seed": 8}).json()
    assert second["alert_confirmed"] is True


def test_bad_scenario_400(client):
    assert client.post("/simulate/nope").status_code == 400


def test_empty_ingest_422(client):
    assert client.post("/ingest", json={"transactions": []}).status_code == 422


def test_ingest_bad_columns_400(client):
    r = client.post("/ingest", json={"transactions": [{"foo": 1}] * 600})
    assert r.status_code == 400 and "missing columns" in r.json()["detail"]


def test_ingest_roundtrip(client):
    from simulation.fraud_gen import get_batch
    tx = get_batch(600, "normal", seed=5).to_dict("records")
    r = client.post("/ingest", json={"transactions": tx, "scenario": "live"}).json()
    assert r["batch_id"] == 1 and r["severity"] in ("none", "mild")
    scores = client.get("/scores").json()["scores"]
    assert len(scores) == 1 and scores[0]["scenario"] == "live"


def test_reset_restarts_numbering(client):
    client.post("/simulate/normal", params={"n": 800, "seed": 1})
    client.post("/reset")
    r = client.post("/simulate/normal", params={"n": 800, "seed": 1}).json()
    assert r["batch_id"] == 1


def test_outputs_track_accuracy_decay(client):
    n = client.post("/simulate/normal", params={"n": 800, "seed": 21}).json()["outputs"]
    s = client.post("/simulate/spike", params={"n": 800, "seed": 22}).json()["outputs"]
    assert n["acc"] > 0.8, n
    assert s["acc"] < n["acc"] - 0.2, (n, s)  # concept drift: model goes blind
    assert s["true_fraud_rate"] > s["pred_fraud_rate"], s
    assert {"psi_conf", "mean_conf", "acc_drop"} <= set(s)


def test_scores_include_outputs(client):
    client.post("/simulate/normal", params={"n": 800, "seed": 31})
    body = client.get("/scores").json()
    assert body["baseline_acc"] > 0.8
    assert len(body["outputs"]) == 1 and body["outputs"][0]["acc"] is not None


def test_distributions_overlay(client):
    client.post("/simulate/spike", params={"n": 800, "seed": 41})
    d = client.get("/distributions", params={"feature": "location"}).json()
    assert d["kind"] == "categorical" and d["latest"] is not None
    assert abs(sum(d["latest"]["values"]) - 1.0) < 0.01
    n = client.get("/distributions", params={"feature": "amount"}).json()
    assert n["kind"] == "numeric" and len(n["axis"]) == len(n["baseline"]["values"]) + 1
    assert client.get("/distributions", params={"feature": "nope"}).status_code == 400


def test_alerts_lists_confirmed(client):
    assert client.get("/alerts").json()["alerts"] == []
    client.post("/simulate/spike", params={"n": 800, "seed": 51})
    client.post("/simulate/spike", params={"n": 800, "seed": 52})
    alerts = client.get("/alerts").json()["alerts"]
    assert len(alerts) == 2 and all(a["severity"] == "severe" for a in alerts)
