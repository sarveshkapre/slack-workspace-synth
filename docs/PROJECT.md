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

## Next 3 improvements
1. Add streaming export to JSONL/S3.
2. Add channel membership + DM threads.
3. Add richer file metadata + file body generation.
