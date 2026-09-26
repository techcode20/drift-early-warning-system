# Drift Guard — Concept-Drift Early Warning for Live ML Models

> **Tagline:** Catch your model rotting before your users do. *Silent drift. Loud alarm.*

Deployed models decay silently as live data shifts away from training data.
Drift Guard snapshots Day-0 distributions, scores every incoming batch with
PSI / KS statistics, plots a rolling health line, blames the top-drifting
feature, and escalates by severity — with a 2-consecutive-breach confirmation
rule so it doesn't cry wolf.

## 60-second demo

```bash
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000/ and press **▶ Auto-demo**
(4 normal → 4 gradual → 2 spike), or feed manually. Watch the health line
go flat → climb → spike, with a red **DRIFT DETECTED — Feature: location** banner.

## How it works

```
simulation/fraud_gen.py  →  detector/ (PSI/KS/KL + severity)
  baseline + batches (labeled)       │ {psi_global, severity, top_feature}
        │                            ▼
        │                  simulation/model.py (dummy fraud classifier)
        │                            │ {acc, fraud rates, confidence PSI}
        ▼                            ▼
backend/main.py  →  SQLite (batches, drift_scores, feature_scores,
                             output_scores, histograms)
        │ GET /scores /distributions /alerts
        ▼
frontend/ (health line + model-damage chart + mugshot-vs-lineup overlay)
```

- **Baseline:** 10k transactions define "normal" (quantile bins frozen at deploy time).
- **Model:** a LogisticRegression trained on baseline stands in for the deployed
  model — good on its own world, blind when fraudsters change tactics.
- **Two drift flavours:** `gradual` shifts inputs only (covariate shift — accuracy
  survives); `spike` changes the fraud rule itself (concept drift — accuracy collapses).
- **Score:** global PSI = **max** per-feature PSI (one rotting feature can't hide behind healthy ones).
- **Bands:** `<0.10` none · `0.10–0.25` mild · `0.25–0.50` moderate · `≥0.50` severe.
- **Confirmation:** lone breach is logged; 2 consecutive moderate/severe breaches → alert **✓ confirmed**.
- **Noise guards:** batches < 500 rows refused (`no-decision`), KS p-values Bonferroni-corrected.
- **Actions:** none/mild → log · moderate → alert-human · severe → `retrain_trigger.json`.

## API

| Method & path | Purpose |
|---|---|
| `GET /health` | liveness + baseline rows + batch count |
| `POST /baseline/load?n=` | rebuild baseline (n ≥ 1000) |
| `POST /ingest` | score a real batch `{transactions[], scenario}` → 201 |
| `POST /simulate/{normal\|gradual\|spike}?n=&seed=` | one-click synthetic feed for demos |
| `GET /scores?limit=` | rolling scores + per-feature PSI + outputs (with `confirmed` flags) |
| `GET /distributions?feature=` | baseline vs latest-batch histogram (mugshot vs lineup) |
| `GET /alerts` | confirmed moderate/severe breaches, newest first |
| `POST /reset` | clear history, restart numbering (fresh demo) |

Errors are meaningful: bad columns → 400, empty batch → 422, bad scenario → 400.

## Project layout (team roles)

| Folder | Owner | Contents |
|---|---|---|
| `simulation/` | M1 data | `fraud_gen.py` — baseline/normal/gradual/spike generator |
| `detector/` | M2 stats | `metrics.py` (PSI/KS/KL), `drift_engine.py` (severity, confirmation), `test_metrics.py` |
| `backend/` | M3 API | `main.py` (FastAPI), `db.py` (SQLite store), `test_api.py` |
| `frontend/` | M4 UI | D3.js dashboard (`index.html`, `app.js`, `style.css`) |
| `shared/` | all | `config.py` thresholds, `schema.json` contracts |

`DRIFT_DB` env var overrides the SQLite path (tests use a temp file).

## Verify

```bash
python -m pytest detector backend simulation -q   # 30 tests: stats + model + API + confirmation rule
```

CI (`.github/workflows/ci.yml`) runs the same suite on every push to `main`.
