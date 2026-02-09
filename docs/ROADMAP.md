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

## Next
- Slack API hardening: shared retry/backoff, better reports, and safer defaults for large runs
- DB safety: schema/metadata validation gates and read-only server open modes
- Incremental export/import (append-style sync with dedupe keys)
- Performance baselines (bench scripts + documented targets)
