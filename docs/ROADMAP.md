# ROADMAP

## MVP (v0.1.x)
- Deterministic generator with seed
- SQLite store
- CLI + API
- Plugin hooks

## Shipped (v0.1.x follow-ons)
- Channel membership + DM/MPDM threads
- JSONL import/export
- Cursor-based API pagination
- Enterprise Grid seeding guide (Entra SCIM + per-user OAuth + optional bulk import)
- Slack seeding/provisioning helpers (channel-map, provision-slack, seed-live)
- Slack API hardening (retry/backoff + safer defaults + richer machine-readable reports)
- DB safety gates (`validate-db`, fail-fast server startup, read-only DB opens)
- Performance baselines (local benchmark script + documented workflow)

## Next
- Incremental export/import (append-style sync with dedupe keys)
- Credentialed Slack sandbox smoke run for `channel-map`/`provision-slack`/`seed-live` (optional CI or release checklist)
