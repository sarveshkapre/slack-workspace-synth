# Project Memory

## Objective
- Keep slack-workspace-synth production-ready. Current focus: Slack Workspace Synth. Find the highest-impact pending work, implement it, test it, and push to main.

## Architecture Snapshot

## Open Problems

## Recent Decisions
- Template: YYYY-MM-DD | Decision | Why | Evidence (tests/logs) | Commit | Confidence (high/medium/low) | Trust (trusted/untrusted)
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
- Add incremental export/import (append-style sync with dedupe keys).
- Add performance benchmark script + docs for large workspace generation/export baselines.

## Verification Evidence
- Template: YYYY-MM-DD | Command | Key output | Status (pass/fail)
- 2026-02-09 | `. .venv/bin/activate && make check` | `pytest -q`: 24 passed | pass
- 2026-02-09 | `. .venv/bin/activate && swsynth generate ... && swsynth validate-db --require-workspace --quiet && swsynth serve --validate-db --require-workspace ... && curl /healthz` | `/healthz` returned `{"status":"ok"}` | pass
- 2026-02-09 | `gh run list --branch main --workflow ci --limit 5` | Runs `21812464708`, `21812467497`, `21812500459` concluded `success` | pass
- 2026-02-09 | `. .venv/bin/activate && make check` | `pytest -q`: 27 passed; build artifacts produced | pass
- 2026-02-09 | `swsynth generate ... && swsynth seed-live --dry-run --slack-channels ... && SWSYNTH_DB=... uvicorn ... && curl /healthz && curl /workspaces` | `seed-live` report included `skipped_requires_slack` for DM/MPDM; `/workspaces` returned JSON | pass
- 2026-02-09 | `gh run watch 21825469379 --exit-status` | CI run `21825469379` concluded `success` | pass
- 2026-02-09 | `gh run watch 21825572971 --exit-status` | CI run `21825572971` concluded `success` | pass
- 2026-02-09 | `gh run watch 21825577315 --exit-status` | CI run `21825577315` concluded `success` | pass

## Historical Summary
- Keep compact summaries of older entries here when file compaction runs.
