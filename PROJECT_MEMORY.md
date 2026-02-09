# Project Memory

## Objective
- Keep slack-workspace-synth production-ready. Current focus: Slack Workspace Synth. Find the highest-impact pending work, implement it, test it, and push to main.

## Architecture Snapshot

## Open Problems

## Recent Decisions
- Template: YYYY-MM-DD | Decision | Why | Evidence (tests/logs) | Commit | Confidence (high/medium/low) | Trust (trusted/untrusted)
- 2026-02-09 | Add `export-jsonl --messages-after-ts/--files-after-ts` filters for incremental exports | Supports append-style sync workflows by letting operators export only newer messages/files without rewriting full JSONL sets | `make check` (30 passed) + CLI smoke verified filtered JSONL files can be empty and still write correctly | c1759c7 | high | trusted
- 2026-02-09 | Add `seed-import --validate` to validate on-disk (and optional zip) import bundle artifacts | Makes bulk import workflows safer by failing fast when required artifacts are missing or malformed | `make check` (30 passed) + CLI smoke `seed-import --zip-out ... --validate` succeeded | fe6c4bd | high | trusted
- 2026-02-09 | Align package versioning + changelog to `0.1.3` | Eliminates version skew between `pyproject.toml` and `slack_workspace_synth.__version__`, and makes built artifacts match documented release notes | `make check` built `slack_workspace_synth-0.1.3*` artifacts successfully | 56aa2ce | high | trusted
- 2026-02-09 | Add `import-jsonl --mode append` to dedupe by primary key when importing into an existing DB | Enables repeatable export/import workflows without DB rebuilds; makes it safe to re-run imports and supports append-style sync patterns | `make check` (29 passed) + `tests/test_cli_import.py` + local smoke import + append import | e24ac6a | high | trusted
- 2026-02-09 | Add `seed-import --zip/--zip-out` to emit Slack export-style `.zip` bundles | Many adjacent tools consume Slack exports as zips; emitting a zip improves interoperability for viewer and migration test workflows | `make check` (29 passed) + `tests/test_cli_seed_import.py` + local smoke created `import_bundle.zip` | 0833cef | high | trusted
- 2026-02-09 | Add local benchmark script + docs (`scripts/bench.py`, `docs/BENCHMARKS.md`) and update roadmap | Benchmarks help catch perf regressions and set operator expectations; roadmap should reflect shipped baseline tooling | `make check` (29 passed) + local smoke ran `python scripts/bench.py --profile quick` and wrote `report.json` | 566aa4e | medium | trusted
- 2026-02-09 | Harden `seed-live` dry-run to guarantee zero Slack API calls and enrich the report with mapping coverage + skip reasons | Dry-run must be safe for clickops planning; DM/MPDM opens and channel-map fetch/create are real Slack calls and should never happen in dry-run | `make check` (27 passed) + local smoke (`seed-live --dry-run` with DM/MPDM present produced `skipped_requires_slack` and `skip_reasons`) | ff66ccd | high | trusted
- 2026-02-09 | Open FastAPI API SQLite connections in read-only mode and return HTTP 400 for missing/invalid DB paths | Prevent server queries from mutating unknown/production DBs and avoid surprising schema initialization on bad paths | `make check` (27 passed) + `tests/test_api_cursor.py` + API smoke (`curl /workspaces` against `SWSYNTH_DB`) | d7ea972 | high | trusted
- 2026-02-09 | Add shared Slack API retry/backoff (429 Retry-After, transient 5xx/URLError, ok:false ratelimited) with tuning flags on Slack CLI commands | Slack rate limiting and transient failures are normal in real workspaces; retries/backoff makes seeding/provisioning materially more reliable | `make check` (24 passed) + `tests/test_slack_retry.py` + local smoke path | 5899503 | high | trusted
- 2026-02-09 | Add `swsynth validate-db` plus `serve --validate-db` and record `schema_version` in workspace meta | Fail fast when pointing at the wrong DB and establish a forward-compatibility hook for future schema evolution | `tests/test_cli_validate_db.py` + local `swsynth validate-db --require-workspace` smoke | 5899503 | high | trusted
- 2026-02-09 | Refresh roadmap/project/README docs to match shipped features and new validation guidance | Reduce operator confusion and keep “Next” lists meaningful | Doc diffs (`README.md`, `docs/ROADMAP.md`, `docs/PROJECT.md`, `docs/CHANGELOG.md`) | ee5b095 | high | trusted

## Mistakes And Fixes
- Template: YYYY-MM-DD | Issue | Root cause | Fix | Prevention rule | Commit | Confidence
- 2026-02-09 | CI failure: CLI test asserted plain-text error message but Typer emitted ANSI-styled output in GitHub Actions | Brittle substring match against colorized output | Strip ANSI sequences before matching error text | In CLI tests, normalize output by stripping ANSI codes before assertions | ab8640f | high

## Known Risks
- Slack integration paths were not exercised against a real Slack workspace in this cycle (no credentials available in automation). Next step is a credentialed Slack sandbox smoke check to validate scopes, rate-limit behavior, and error handling end-to-end.

## Next Prioritized Tasks
- Add credentialed Slack sandbox smoke run (CI optional or release checklist) for `channel-map`/`provision-slack`/`seed-live`.
- Add incremental export modes to pair with append imports (sync only new rows using cursors/timestamps).
- Add `seed-import` output validation to ensure required Slack export artifacts exist (fail fast before shipping bundles).
- Start tracking benchmark baselines over time (targets + regression notes).

## Verification Evidence
- Template: YYYY-MM-DD | Command | Key output | Status (pass/fail)
- 2026-02-09 | `. .venv/bin/activate && make check` | `pytest -q`: 30 passed; build produced `slack_workspace_synth-0.1.3*` artifacts | pass
- 2026-02-09 | `swsynth generate ... && swsynth export-jsonl --messages-after-ts <max_ts> --files-after-ts <max_ts> && swsynth seed-import --zip-out ... --validate` | Export wrote empty filtered `messages.jsonl`/`files.jsonl`; seed-import validated + wrote zip | pass
- 2026-02-09 | `gh run watch 21842776442 --exit-status` | CI concluded `success` for commit `c1759c7` | pass
- 2026-02-09 | `gh run watch 21842856318 --exit-status` | CI concluded `success` for commit `fe6c4bd` | pass
- 2026-02-09 | `gh run watch 21842931635 --exit-status` | CI concluded `success` for commit `56aa2ce` | pass
- 2026-02-09 | `. .venv/bin/activate && make check` | `pytest -q`: 24 passed | pass
- 2026-02-09 | `. .venv/bin/activate && swsynth generate ... && swsynth validate-db --require-workspace --quiet && swsynth serve --validate-db --require-workspace ... && curl /healthz` | `/healthz` returned `{"status":"ok"}` | pass
- 2026-02-09 | `gh run list --branch main --workflow ci --limit 5` | Runs `21812464708`, `21812467497`, `21812500459` concluded `success` | pass
- 2026-02-09 | `. .venv/bin/activate && make check` | `pytest -q`: 27 passed; build artifacts produced | pass
- 2026-02-09 | `swsynth generate ... && swsynth seed-live --dry-run --slack-channels ... && SWSYNTH_DB=... uvicorn ... && curl /healthz && curl /workspaces` | `seed-live` report included `skipped_requires_slack` for DM/MPDM; `/workspaces` returned JSON | pass
- 2026-02-09 | `gh run watch 21825469379 --exit-status` | CI run `21825469379` concluded `success` | pass
- 2026-02-09 | `gh run watch 21825572971 --exit-status` | CI run `21825572971` concluded `success` | pass
- 2026-02-09 | `gh run watch 21825577315 --exit-status` | CI run `21825577315` concluded `success` | pass
- 2026-02-09 | `gh run watch 21825623371 --exit-status` | CI run `21825623371` concluded `success` | pass
- 2026-02-09 | `. .venv/bin/activate && make check` | `pytest -q`: 29 passed | pass
- 2026-02-09 | `. .venv/bin/activate && swsynth generate ... && swsynth export-jsonl ... && swsynth import-jsonl ... && swsynth import-jsonl --mode append ... && swsynth seed-import --zip-out ... && python scripts/bench.py --profile quick ...` | `swsynth stats` printed expected counts; bench wrote `report.json` | pass
- 2026-02-09 | `gh run watch 21834239914 --exit-status` | CI run `21834239914` concluded `success` | pass
- 2026-02-09 | `gh run watch 21834323376 --exit-status` | CI run `21834323376` concluded `success` | pass
- 2026-02-09 | `gh run watch 21834464863 --exit-status` | CI run `21834464863` concluded `success` | pass
- 2026-02-09 | `gh run watch 21834581856 --exit-status` | CI run `21834581856` concluded `success` | pass
- 2026-02-09 | `gh run watch 21834639304 --exit-status` | CI run `21834639304` concluded `success` | pass

## Historical Summary
- Keep compact summaries of older entries here when file compaction runs.
