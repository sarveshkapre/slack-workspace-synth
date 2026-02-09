# Clone Feature Tracker

## Context Sources
- README and docs
- TODO/FIXME markers in code
- Test and build failures
- Gaps found during codebase exploration

## Candidate Features To Do
Scoring lens (rough): Impact | Effort | Strategic Fit | Differentiation | Risk | Confidence (1-5 each).

### Backlog
- [ ] P2 (3|3|4|3|2|3): Add a Slack sandbox integration smoke check (credentialed) for `channel-map`/`provision-slack`/`seed-live` in CI or release checklist.
- [ ] P2 (3|4|3|3|3|2): Add incremental export/import mode with dedupe keys for append-style sync workflows.
- [ ] P3 (2|3|3|2|2|3): Add performance benchmark script + docs for large workspace generation/export baselines.

## Implemented
- [x] 2026-02-09: Hardened `seed-live --dry-run` to guarantee zero Slack API calls (including DM/MPDM opens and
  channel-map fetch/create), plus richer machine-readable report fields for safer rollout planning
  (`src/slack_workspace_synth/cli.py`, `tests/test_cli_seed_live.py`) (commits `ff66ccd`).
- [x] 2026-02-09: Opened FastAPI API SQLite connections in read-only mode and return HTTP 400 for missing/invalid DB
  paths (no schema/PRAGMA mutation) (`src/slack_workspace_synth/api.py`, `src/slack_workspace_synth/storage.py`,
  `tests/test_api_cursor.py`) (commit `d7ea972`).
- [x] 2026-02-09: Added shared Slack API retry/backoff helper and wired it into `seed-live`, `channel-map`,
  and `provision-slack` (new CLI knobs: `--slack-max-retries`, `--slack-timeout-seconds`,
  `--slack-max-backoff-seconds`) (`src/slack_workspace_synth/cli.py`, `tests/test_slack_retry.py`).
- [x] 2026-02-09: Added `swsynth validate-db` plus `swsynth serve --validate-db` and started recording
  `schema_version` in workspace meta (`src/slack_workspace_synth/cli.py`,
  `src/slack_workspace_synth/storage.py`, `tests/test_cli_validate_db.py`).
- [x] 2026-02-09: Refreshed stale roadmap/project docs and README guidance (`docs/ROADMAP.md`,
  `docs/PROJECT.md`, `docs/CHANGELOG.md`, `README.md`).
- [x] 2026-02-08: Fixed CI packaging failure by updating `Makefile` build fallback logic to handle missing `wheel`/`setuptools` safely (`Makefile`).
- [x] 2026-02-08: Fixed Slack channels loader to accept top-level array payloads for `--slack-channels` (`src/slack_workspace_synth/cli.py`, `tests/test_cli_channel_map.py`).
- [x] 2026-02-08: Added fail-fast generation validation for invalid counts, membership bounds, and batch size (`src/slack_workspace_synth/cli.py`, `tests/test_cli_generate_validation.py`).
- [x] 2026-02-08: Added `provision-slack --report` JSON evidence output (`src/slack_workspace_synth/cli.py`, `tests/test_cli_provision_slack.py`).
- [x] 2026-02-08: Updated product memory/docs for behavior changes (`README.md`, `docs/CHANGELOG.md`).
- [x] 2026-02-08: Upgraded GitHub Actions CodeQL action from `v3` to `v4` (`.github/workflows/ci.yml`).
- [x] Verification 2026-02-09: `. .venv/bin/activate && make check` (pass; lint, mypy, pytest 24 passed, build success).
- [x] Verification 2026-02-09: Local CLI smoke flow (`swsynth generate`, `swsynth validate-db --require-workspace`,
  `swsynth serve --validate-db --require-workspace`, `curl /healthz`) completed with expected outputs.
- [x] Verification 2026-02-08: `. .venv/bin/activate && pytest -q tests/test_cli_channel_map.py tests/test_cli_generate_validation.py tests/test_cli_provision_slack.py` (pass, 6 tests).
- [x] Verification 2026-02-08: `. .venv/bin/activate && make check` (pass; lint, mypy, pytest 19 passed, build success).
- [x] Verification 2026-02-08: Local CLI smoke flow (`swsynth generate`, `swsynth stats`, `swsynth channel-map`, `swsynth provision-slack --dry-run --report`) completed with expected outputs.
- [x] Verification 2026-02-08: GitHub Actions runs succeeded for pushed commits `c42e3de`, `965b38a`, `a83578f`, and `2709ab6` (run IDs `21807092238`, `21807093711`, `21807095744`, `21807158787`).

## Insights
- CI failures from runs `21617680408` through `21618554925` all had the same root cause: `make build` invoked `python -m build --no-isolation` without `wheel` installed in the active venv.
- Slack channel export payloads are not consistently wrapped; accepting top-level arrays removes friction for offline mapping/provisioning.
- Machine-readable run reports improve repeatability and provide evidence for autonomous maintenance loops.
- CI emitted a CodeQL deprecation annotation; proactive action upgrades reduce future breakage risk.
- Market scan (untrusted): Slack Web API rate limiting is expected behavior (429 + `Retry-After`), and Slack’s docs explicitly recommend handling retries/backoff; this is table-stakes for any real Slack seeding/provisioning flow. Sources: https://docs.slack.dev/apis/web-api/rate-limits/, https://api.slack.com/docs/rate-limits
- Market scan (untrusted): Slack exports have a fairly predictable artifact layout (channels, DMs, users, etc); adjacent tools emphasize “view/search/forensics”, implying export-compatibility and stable output shapes are a common expectation even when the generator is synthetic. Sources: https://slack.com/help/articles/201658943-Export-your-workspace-data, https://github.com/Slacksky/viewexport, https://github.com/rusq/slackdump

## Notes
- This file is maintained by the autonomous clone loop.

### Auto-discovered Open Checklist Items (2026-02-08)
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] `make check`
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] Update `docs/CHANGELOG.md`
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] Tag release (SemVer)
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] Create GitHub Release with notes
