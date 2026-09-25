# AGENTS.md

> State as of 2026-09-24: greenfield — working directory is empty. No `README`, manifests, lockfiles, source, tests, CI, or `opencode.json` exist yet. Do not assume a stack. When one is added, replace this stub with exact commands and entrypoints.

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
