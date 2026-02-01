# Update

## Shipped (2026-02-01)
- CLI: `swsynth export-jsonl` to stream JSONL exports (optionally gzipped).
- API: cursor/keyset pagination for `users`, `channels`, `messages`, and `files` via `cursor` + `X-Next-Cursor`.
- Storage: added supporting indexes for keyset pagination.
- CLI: `swsynth stats` for quick workspace counts (optionally writes summary JSON).
- SQLite: persist per-workspace `meta` (seed, requested sizes, plugins, generator version) and include it in summary output.
- CLI: `swsynth import-jsonl` to ingest JSONL exports into SQLite.

## How to verify
```bash
make check
```

## How to try
```bash
. .venv/bin/activate
swsynth generate --db ./data/demo.db --seed 42 --messages 1000 --files 200
swsynth export-jsonl --db ./data/demo.db --out ./export --compress
swsynth serve --db ./data/demo.db --host 127.0.0.1 --port 8080
```

Cursor pagination example:
```bash
curl -i "http://127.0.0.1:8080/workspaces/<workspace_id>/messages?cursor=&limit=100"
```

## Notes
- Per request: no PRs created/updated; work is committed directly on `main`.
