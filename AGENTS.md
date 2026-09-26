# AGENTS.md

> Stack: Python 3.12 + FastAPI + SQLite + scipy + D3.js. Repo: techcode20/drift-early-warning-system.

## Commands (run from repo root, `python -m` form — bare `uvicorn`/`pytest` may miss PATH)

- Install: `python -m pip install -r requirements.txt`
- Tests: `python -m pytest detector backend -q` (must stay green; CI runs same)
- API: `python -m uvicorn backend.main:app --reload` → dashboard `/`, docs `/docs`
- E2E demo: `POST /reset` → feed `/simulate/normal|gradual|spike` → check `GET /scores`

## Boundaries

- `DRIFT_DB` env overrides SQLite path — tests use temp DB; never commit `*.db`, `*.csv`, `retrain_trigger.json` (gitignored).
- Thresholds live ONLY in `shared/config.py`; detector stays pure (no DB/API imports).
- Commit/push only when explicitly asked. Keep `practice/`-style scratch outside the repo.


## Shell (verified env: `win32`, PowerShell 5.1)

- Run terminal ops via `bash` tool only; file ops via `read` / `write` / `edit` / `glob` / `grep`.
- Do not `cd` inside commands — pass `workdir` instead.
- Chain dependent commands with `; if ($?) { ... }` (`&&` is not supported).
- Quote paths with spaces: `& "path with spaces\script.ps1"`.
- Scratch space: `C:\Users\lenovo\AppData\Local\Temp\opencode` (pre-approved, already exists).

## Workflow

- Verify before claiming done: reproduce via build/test/lint output, not narration.
- Prefer executable sources of truth (`package.json` scripts, configs, CI) over prose docs.
- Keep this file compact: only repo-specific commands, boundaries, and gotchas an agent would otherwise guess wrong.
