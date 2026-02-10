# PROJECT

## Setup
```bash
make setup
```

## Development
```bash
make dev
```

## Generate data (CLI)
```bash
. .venv/bin/activate
swsynth generate --workspace "Acme Demo" --users 2000 --channels 80 --messages 120000 --files 5000 --seed 42 --db ./data/acme.db
```

## Run API
```bash
. .venv/bin/activate
swsynth serve --db ./data/acme.db --host 0.0.0.0 --port 8080
```

## Export to JSONL
```bash
. .venv/bin/activate
swsynth export-jsonl --db ./data/acme.db --out ./export
```
For append-style incremental runs, you can track max timestamps automatically:
```bash
. .venv/bin/activate
swsynth export-jsonl --db ./data/acme.db --out ./export --incremental-state ./export_state.json
```

## Import from JSONL
```bash
. .venv/bin/activate
swsynth import-jsonl --source ./export --db ./data/imported.db
```
Append/dedupe into an existing DB:
```bash
. .venv/bin/activate
swsynth import-jsonl --source ./export --db ./data/imported.db --mode append
```

## Stats
```bash
. .venv/bin/activate
swsynth stats --db ./data/acme.db
```

## Test
```bash
make test
```

## Lint
```bash
make lint
```

## Typecheck
```bash
make typecheck
```

## Build
```bash
make build
```

## Quality gate
```bash
make check
```

## Release
```bash
make release
```

## Slack Sandbox Smoke Check (Credentialed)
This verifies Slack API connectivity and basic scopes (`auth.test` + `conversations.list`).
```bash
SLACK_SMOKE_TOKEN=xoxp-... make slack-smoke
```

## Next 3 improvements
1. Add a credentialed Slack sandbox smoke run (release checklist or optional CI) for `channel-map`/`provision-slack`/`seed-live`.
2. Add incremental export modes to pair with append imports (sync only new rows).
3. Start tracking benchmark baselines over time (targets + regression notes).
