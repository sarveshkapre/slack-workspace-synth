# Clone Feature Tracker

## Context Sources
- README and docs
- TODO/FIXME markers in code
- Test and build failures
- Gaps found during codebase exploration

## Candidate Features To Do
Scoring lens (rough): Impact | Effort | Strategic Fit | Differentiation | Risk | Confidence (1-5 each).

### Backlog
- [ ] P3 (2|2|3|2|1|4): Add `make smoke` to run a minimal local end-to-end flow (generate, validate-db, export, import append) for fast operator verification.
- [ ] P3 (2|2|3|2|2|3): Add a lightweight performance regression note in `docs/BENCHMARKS.md` with “expected ranges” and how to capture/compare results.

## Implemented
- [x] 2026-02-10: `export-jsonl` now emits `export_manifest.json` (row counts + filters + max timestamps) for more observable incremental pipelines (`src/slack_workspace_synth/cli.py`, `src/slack_workspace_synth/storage.py`, `tests/test_cli_export_jsonl_filters.py`) (commit `5a5d0b2`).
- [x] 2026-02-10: Added `export-jsonl --incremental-state` (auto-tracks max message/file timestamps) and extended
  export summaries with max timestamps (`src/slack_workspace_synth/cli.py`, `src/slack_workspace_synth/storage.py`,
  `tests/test_cli_export_jsonl_filters.py`) (commits `9525212`, `cece02b`).
- [x] 2026-02-10: `seed-import` now emits an empty `content_flags.json` placeholder and validates it (`src/slack_workspace_synth/cli.py`,
  `tests/test_cli_seed_import.py`) (commit `3ca2aa0`).
- [x] 2026-02-10: Added `make clean` for removing build/test artifacts without touching user data (`Makefile`) (commit `2be26fa`).
- [x] 2026-02-10: Added a credentialed Slack API smoke check (`swsynth slack-smoke` + `make slack-smoke`) and updated
  docs/release checklist (`src/slack_workspace_synth/cli.py`, `Makefile`, `docs/RELEASE.md`, `docs/ROADMAP.md`,
  `docs/PROJECT.md`) (commit `534ddd0`).
- [x] 2026-02-09: `seed-import` now emits empty `integration_logs.json` and `canvases.json` placeholders for better
  export-tool compatibility (`src/slack_workspace_synth/cli.py`, `tests/test_cli_seed_import.py`) (commit `38a5aea`).
- [x] 2026-02-09: Added incremental JSONL export filters for messages/files via `export-jsonl --messages-after-ts` and
  `--files-after-ts` (`src/slack_workspace_synth/cli.py`, `src/slack_workspace_synth/storage.py`,
  `tests/test_cli_export_jsonl_filters.py`) (commit `c1759c7`).
- [x] 2026-02-09: Added `seed-import --validate` to ensure required export artifacts exist (and validate the zip when
  produced) (`src/slack_workspace_synth/cli.py`, `tests/test_cli_seed_import.py`) (commit `fe6c4bd`).
- [x] 2026-02-09: Aligned package versioning and changelog (bumped to `0.1.3`, cut a `v0.1.3` changelog section)
  (`pyproject.toml`, `src/slack_workspace_synth/__init__.py`, `docs/CHANGELOG.md`) (commit `56aa2ce`).
- [x] 2026-02-09: Added `import-jsonl --mode append` to dedupe by primary key when importing into an existing DB
  (`src/slack_workspace_synth/cli.py`, `src/slack_workspace_synth/storage.py`, `tests/test_cli_import.py`)
  (commit `e24ac6a`).
- [x] 2026-02-09: Added `seed-import --zip/--zip-out` to emit a Slack export-style `.zip` bundle
  (`src/slack_workspace_synth/cli.py`, `tests/test_cli_seed_import.py`) (commit `0833cef`).
- [x] 2026-02-09: Added a local benchmark script + docs for generation + JSONL export baselines
  (`scripts/bench.py`, `docs/BENCHMARKS.md`, `Makefile`) (commit `566aa4e`).
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
- [x] Verification 2026-02-09: `. .venv/bin/activate && make check` (pass; lint, mypy, pytest 29 passed, build success).
- [x] Verification 2026-02-09: Local CLI smoke flow (`swsynth generate`, `swsynth export-jsonl`,
  `swsynth import-jsonl`, `swsynth import-jsonl --mode append`, `swsynth seed-import --zip-out`,
  `python scripts/bench.py --profile quick`) completed with expected outputs.
- [x] Verification 2026-02-09: GitHub Actions runs succeeded for pushed commits `e24ac6a`, `0833cef`, `566aa4e`
  (run IDs `21834239914`, `21834323376`, `21834464863`).

## Insights
- CI failures from runs `21617680408` through `21618554925` all had the same root cause: `make build` invoked `python -m build --no-isolation` without `wheel` installed in the active venv.
- Slack channel export payloads are not consistently wrapped; accepting top-level arrays removes friction for offline mapping/provisioning.
- Machine-readable run reports improve repeatability and provide evidence for autonomous maintenance loops.
- CI emitted a CodeQL deprecation annotation; proactive action upgrades reduce future breakage risk.
- Market scan (untrusted): Slack Web API rate limiting is expected behavior (429 + `Retry-After`), and Slack’s docs explicitly recommend handling retries/backoff; this is table-stakes for any real Slack seeding/provisioning flow. Sources: https://docs.slack.dev/apis/web-api/rate-limits/, https://api.slack.com/docs/rate-limits
- Market scan (untrusted): Slack exports have a fairly predictable artifact layout (channels, DMs, users, etc); adjacent tools emphasize “view/search/forensics”, implying export-compatibility and stable output shapes are a common expectation even when the generator is synthetic. Sources: https://slack.com/help/articles/201658943-Export-your-workspace-data, https://github.com/Slacksky/viewexport, https://github.com/rusq/slackdump
- Market scan (untrusted): Slack’s export ZIP format includes reference JSON files beyond channels/users (e.g. `integration_logs.json`, `canvases.json`, optional `content_flags.json` on some plans); emitting placeholders improves interoperability with export consumers. Source: https://slack.com/help/articles/220556107-How-to-read-Slack-data-exports
- Market scan (untrusted): Many adjacent tools consume Slack exports as `.zip` bundles; emitting a zip improves interoperability for viewer and migration test workflows. Sources: https://slack.com/help/articles/201658943-Export-your-workspace-data, https://viewexport.com/, https://github.com/hfaran/slack-archive-viewer
- Market scan (untrusted): Export viewers tend to assume “drop a zip/folder and browse/search”; supporting the common
  export layout and stable file naming improves interoperability even for synthetic generators. Sources:
  https://github.com/hfaran/slack-export-viewer, https://github.com/Slacksky/viewexport

## Notes
- This file is maintained by the autonomous clone loop.

### Auto-discovered Open Checklist Items (2026-02-08)
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] `make check`
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] Update `docs/CHANGELOG.md`
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] Tag release (SemVer)
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] Create GitHub Release with notes
