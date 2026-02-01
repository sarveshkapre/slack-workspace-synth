# CHANGELOG

## v0.1.1
- Added `swsynth export-jsonl` for streaming JSONL exports (optionally gzipped).
- Added cursor-based pagination for API `users`, `channels`, `messages`, and `files` with `X-Next-Cursor`.
- Added `swsynth stats` for quick workspace counts.
- Added per-workspace generation metadata stored in SQLite and included in summary exports (`meta`).
- Added `swsynth import-jsonl` to load JSONL exports back into SQLite.

## v0.1.0
- Initial MVP: generator, SQLite storage, CLI, FastAPI read-only API, plugin hooks.
