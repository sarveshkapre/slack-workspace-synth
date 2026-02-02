# Slack Workspace Synth

Create a synthetic Slack-like workspace with users, channels, DMs/MPDMs, messages, files, and membership for demos, load testing, or analytics prototyping. Data is deterministic by seed, stored in SQLite, and served via an optional read-only API. Extend generation using a simple plug-in hook API.

## Features
- Deterministic workspace generator (seeded)
- SQLite storage with streaming inserts
- CLI for generation and export
- Optional FastAPI read-only API
- Direct message (IM) + multi-party DM (MPDM) conversations
- Channel membership table for realistic access patterns
- Plug-in hooks to customize entities

## Quickstart
```bash
make setup
make dev
```

Generate a workspace:
```bash
. .venv/bin/activate
swsynth generate --workspace "Acme Demo" --users 2000 --channels 80 --messages 120000 --files 5000 --seed 42 --db ./data/acme.db
```

Generate an enterprise-style workspace with DMs + MPDMs:
```bash
. .venv/bin/activate
swsynth generate --profile enterprise --workspace "Acme Engineering" --seed 42 --db ./data/enterprise.db
```

Export to JSONL:
```bash
. .venv/bin/activate
swsynth export-jsonl --db ./data/acme.db --out ./export --compress
```
The export includes `channel_members.jsonl(.gz)` alongside users, channels, messages, and files.

Import from JSONL:
```bash
. .venv/bin/activate
swsynth import-jsonl --source ./export --db ./data/imported.db
```

Quick stats:
```bash
. .venv/bin/activate
swsynth stats --db ./data/acme.db
```

Run the API:
```bash
swsynth serve --db ./data/acme.db --host 0.0.0.0 --port 8080
```

## API (read-only)
The server reads the DB path from `SWSYNTH_DB` (set by `swsynth serve`). You can also pass `?db=...` on each request.
- `GET /healthz`
- `GET /workspaces`
- `GET /workspaces/{workspace_id}`
- `GET /workspaces/{workspace_id}/users`
- `GET /workspaces/{workspace_id}/channels`
- `GET /workspaces/{workspace_id}/channel-members`
- `GET /workspaces/{workspace_id}/messages`
- `GET /workspaces/{workspace_id}/files`

### Pagination
For large tables, prefer keyset pagination via the `cursor` query param on `users`, `channels`, `messages`, and `files`.
When you pass `cursor`, the server returns `X-Next-Cursor` for the next page.
Do not combine `cursor` and `offset`.

`channels` supports `channel_type` filtering (public/private/im/mpim). `channel-members` supports `channel_id` filtering.

### Reproducibility metadata
`GET /workspaces/{workspace_id}` (and `summary.json` exports) include a `meta` object with the seed, requested sizes, plugins, and generator version.

## Plug-ins
Pass one or more Python module paths using `--plugin`. Each module should expose a `register(registry)` function to attach hooks.

Example:
```bash
swsynth generate --plugin examples.sample_plugin --db ./data/demo.db
```

## Docker
```bash
docker build -t slack-workspace-synth .
docker run --rm -p 8080:8080 -v "$PWD/data:/app/data" slack-workspace-synth \
  swsynth serve --db /app/data/demo.db --host 0.0.0.0 --port 8080
```

## License
MIT
