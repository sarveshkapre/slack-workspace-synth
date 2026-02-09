# Project Memory

## Objective
- Keep slack-workspace-synth production-ready. Current focus: Slack Workspace Synth. Find the highest-impact pending work, implement it, test it, and push to main.

## Architecture Snapshot

## Open Problems

## Recent Decisions
- Template: YYYY-MM-DD | Decision | Why | Evidence (tests/logs) | Commit | Confidence (high/medium/low) | Trust (trusted/untrusted)
- 2026-02-09 | Add shared Slack API retry/backoff (429 Retry-After, transient 5xx/URLError, ok:false ratelimited) with tuning flags on Slack CLI commands | Slack rate limiting and transient failures are normal in real workspaces; retries/backoff makes seeding/provisioning materially more reliable | `make check` (24 passed) + `tests/test_slack_retry.py` + local smoke path | 5899503 | high | trusted
- 2026-02-09 | Add `swsynth validate-db` plus `serve --validate-db` and record `schema_version` in workspace meta | Fail fast when pointing at the wrong DB and establish a forward-compatibility hook for future schema evolution | `tests/test_cli_validate_db.py` + local `swsynth validate-db --require-workspace` smoke | 5899503 | high | trusted
- 2026-02-09 | Refresh roadmap/project/README docs to match shipped features and new validation guidance | Reduce operator confusion and keep “Next” lists meaningful | Doc diffs (`README.md`, `docs/ROADMAP.md`, `docs/PROJECT.md`, `docs/CHANGELOG.md`) | ee5b095 | high | trusted

## Mistakes And Fixes
- Template: YYYY-MM-DD | Issue | Root cause | Fix | Prevention rule | Commit | Confidence

## Known Risks
- Slack integration paths were not exercised against a real Slack workspace in this cycle (no credentials available in automation). Next step is a credentialed Slack sandbox smoke check to validate scopes, rate-limit behavior, and error handling end-to-end.

## Next Prioritized Tasks
- Add richer `seed-live --report` planning output (skip reasons breakdowns, channel type summaries).
- Add credentialed Slack sandbox smoke run (CI optional or release checklist) for `channel-map`/`provision-slack`/`seed-live`.
- Add serve-time safety: optional read-only DB open and stricter DB compatibility gating in API layer.
- Add incremental export/import (append-style sync with dedupe keys).

## Verification Evidence
- Template: YYYY-MM-DD | Command | Key output | Status (pass/fail)
- 2026-02-09 | `. .venv/bin/activate && make check` | `pytest -q`: 24 passed | pass
- 2026-02-09 | `. .venv/bin/activate && swsynth generate ... && swsynth validate-db --require-workspace --quiet && swsynth serve --validate-db --require-workspace ... && curl /healthz` | `/healthz` returned `{"status":"ok"}` | pass
- 2026-02-09 | `gh run list --branch main --workflow ci --limit 5` | Runs `21812464708`, `21812467497`, `21812500459` concluded `success` | pass

## Historical Summary
- Keep compact summaries of older entries here when file compaction runs.
