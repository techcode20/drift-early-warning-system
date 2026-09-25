# Drift Early Warning System ΓÇö Fraud Demo

## Run (3 commands, VS Code terminal)
```
pip install -r requirements.txt
python -m pytest detector/test_metrics.py -v   # Role 2 proof
uvicorn backend.main:app --reload               # then open http://127.0.0.1:8000/
```
In browser: `POST /baseline/load?n=10000` (via /docs), then feed batches, watch D3 health line.

## Folders ΓåÆ Roles
- `simulation/` M1: `python simulation/fraud_gen.py --n 800 --mode gradual|spike`
- `detector/` M2: `metrics.py` (PSI/KS/KL) + `drift_engine.py` (max-PSI global, thresholds 0.1/0.25)
- `backend/` M3: FastAPI `/ingest /scores /baseline/load` + `drift.db`
- `frontend/` M4: D3 health line, polls `/scores` every 2s
- `shared/` all: `schema.json` + `config.py` (do not hardcode thresholds elsewhere)

## Next TODO for team
1. M3: add `POST /simulate/{scenario}` to auto-generate+ingest (so frontend buttons work in one click).
2. M2: add rolling-window (avg last 7) + 2-consecutive-breach rule.
3. M4: per-feature bars from `/scores.features`.
4. All: 30x normal batches = no alert (false-positive check).
