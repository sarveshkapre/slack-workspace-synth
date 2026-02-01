# Slack Workspace Synth — Plan

## Product pitch
Generate a deterministic, Slack-like workspace (users/channels/messages/files) into SQLite for demos, load testing, and analytics prototyping.

## Features (today)
- Deterministic generator (seeded)
- SQLite storage (streaming inserts)
- CLI: `generate`, `serve`, `export-jsonl`
- Read-only FastAPI API
- Plug-in hook system

## Top risks / unknowns
- Very large datasets can stress disk/SQLite performance; requires careful indexing + pragmas + chunking.
- API pagination needs to avoid deep `OFFSET` scans; prefer keyset/cursor pagination.
- Plugin hooks are unbounded; need guidance + guardrails for production-like runs.

## Commands
See `docs/PROJECT.md` for the full command list.

## Shipped (2026-02-01)
- Added `swsynth export-jsonl` to stream JSONL exports (optionally gzipped).
- Added cursor (keyset) pagination for API `users`, `channels`, `messages`, and `files` with `X-Next-Cursor`.
- Added `swsynth stats` for quick workspace counts.
- Added `swsynth import-jsonl` to load JSONL exports back into SQLite.

## Planning memory
- Canonical plan + roadmap live in `docs/PLAN.md` and `docs/ROADMAP.md`.

## Next
- Add channel membership + DM threads.
- Add schema/version metadata for DBs.
- Add incremental export/import (append mode, dedupe).
