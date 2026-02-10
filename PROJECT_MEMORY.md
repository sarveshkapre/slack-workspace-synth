# Project Memory

## Objective
- Keep slack-workspace-synth production-ready. Current focus: Slack Workspace Synth. Find the highest-impact pending work, implement it, test it, and push to main.

## Architecture Snapshot

## Open Problems

## Recent Decisions
- Template: YYYY-MM-DD | Decision | Why | Evidence (tests/logs) | Commit | Confidence (high/medium/low) | Trust (trusted/untrusted)
- 2026-02-10 | Add `export-jsonl --incremental-state` and export max timestamps | Makes append-style export/import workflows less error-prone by auto-tracking the last-seen message/file timestamps and exposing max timestamps in `summary.json` | `make check` (31 passed) + CLI smoke re-ran `export-jsonl --incremental-state` and confirmed second run writes empty incremental `messages.jsonl`/`files.jsonl` | 9525212, cece02b | high | trusted
- 2026-02-10 | `seed-import` emits empty `content_flags.json` placeholder | Some Slack export consumers expect this reference file on certain plans; emitting an empty placeholder improves interoperability without changing bundle semantics | `pytest -q tests/test_cli_seed_import.py` (pass) + `make check` (31 passed) | 3ca2aa0 | high | trusted
- 2026-02-10 | Add `swsynth slack-smoke` + `make slack-smoke` and wire into release checklist | Provides a safe, minimal credentialed Slack API verification path (auth + channel list) that operators can run during release/sandbox setup | `make check` (31 passed) + GitHub Actions run `21858224004` succeeded for the change | 534ddd0 | medium | trusted
- 2026-02-10 | Add `make clean` | Reduces local build/test artifact drift (dist/build/caches) while avoiding deletion of user data directories | `make check` (31 passed) | 2be26fa | high | trusted
- 2026-02-10 | Fix GitHub Actions gitleaks failures by increasing checkout depth | `gitleaks-action` scans `git log` ranges and requires history; `fetch-depth: 1` caused ambiguous revision errors | GitHub Actions run `21858065043` succeeded after setting `fetch-depth: 0` for the gitleaks job | cece02b | high | untrusted
- 2026-02-09 | `seed-import` emits empty `integration_logs.json` and `canvases.json` placeholders | Some Slack export consumers/tools expect these reference files; emitting empty placeholders improves interoperability without changing the core bundle semantics | `make check` (30 passed) + `tests/test_cli_seed_import.py` asserts presence (including zip) | 38a5aea | high | trusted
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
- 2026-02-10 | CI failure on `main` after adding incremental-state support | (1) Pushed without running `make check`, leaving lint/typecheck issues; (2) `gitleaks-action` attempted to scan a `git log` range but checkout used `fetch-depth: 1`, so the parent commit was missing | Fix ruff/mypy issues and set gitleaks checkout `fetch-depth: 0` | Always run `make check` before pushing; for workflows that scan git history/ranges, ensure checkout depth includes required commits | cece02b | high

## Known Risks
- Slack integration paths are still not exercised against a real Slack workspace in this cycle (no credentials available in automation). A credentialed operator can now run `swsynth slack-smoke` / `make slack-smoke` to validate auth/scopes and basic Slack API connectivity, but end-to-end posting/provisioning remains to be smoke-tested in a sandbox.

## Next Prioritized Tasks
- Add export manifests for JSONL runs (table -> rowcount, filters used, max ts) to make incremental pipelines more observable.
- Add `make smoke` to run a minimal local end-to-end flow (generate, validate-db, export, import append) for fast operator verification.
- Start tracking benchmark baselines over time (targets + regression notes).

## Verification Evidence
- Template: YYYY-MM-DD | Command | Key output | Status (pass/fail)
- 2026-02-10 | `. .venv/bin/activate && pytest -q tests/test_cli_seed_import.py` | `2 passed` | pass
- 2026-02-10 | `. .venv/bin/activate && pytest -q tests/test_cli_export_jsonl_filters.py` | `2 passed` | pass
- 2026-02-10 | `. .venv/bin/activate && make check` | `ruff/mypy ok; pytest: 31 passed; build produced 0.1.3 artifacts` | pass
- 2026-02-10 | `. .venv/bin/activate && swsynth generate ... && swsynth validate-db --quiet && swsynth export-jsonl --incremental-state ... (twice) && swsynth seed-import --validate && swsynth serve ... && curl /healthz` | Second `export-jsonl` produced empty incremental slices; `/healthz` returned `{"status":"ok"}` | pass
- 2026-02-10 | `gh run watch 21858065043 --exit-status` | CI concluded `success` after gitleaks fetch-depth fix | pass
- 2026-02-10 | `gh run watch 21858224004 --exit-status` | CI concluded `success` for slack-smoke + docs changes | pass
- 2026-02-10 | `gh run watch 21858333262 --exit-status` | CI concluded `success` for docs tracker updates | pass
- 2026-02-09 | `. .venv/bin/activate && make check` | `pytest -q`: 30 passed; build produced `slack_workspace_synth-0.1.3*` artifacts | pass
- 2026-02-09 | `swsynth generate ... && swsynth export-jsonl --messages-after-ts <max_ts> --files-after-ts <max_ts> && swsynth seed-import --zip-out ... --validate` | Export wrote empty filtered `messages.jsonl`/`files.jsonl`; seed-import validated + wrote zip | pass
- 2026-02-09 | `gh run watch 21842776442 --exit-status` | CI concluded `success` for commit `c1759c7` | pass
- 2026-02-09 | `gh run watch 21842856318 --exit-status` | CI concluded `success` for commit `fe6c4bd` | pass
- 2026-02-09 | `gh run watch 21842931635 --exit-status` | CI concluded `success` for commit `56aa2ce` | pass
- 2026-02-09 | `gh run watch 21843056678 --exit-status` | CI concluded `success` for commit `84216dd` | pass
- 2026-02-09 | `gh run watch 21843127641 --exit-status` | CI concluded `success` for commit `c8a99d4` | pass
- 2026-02-09 | `gh run watch 21843181336 --exit-status` | CI concluded `success` for commit `8c8ed51` | pass
- 2026-02-09 | `gh run watch 21843339136 --exit-status` | CI concluded `success` for commit `38a5aea` | pass
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
