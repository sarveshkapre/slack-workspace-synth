# Clone Feature Tracker

## Context Sources
- README and docs
- TODO/FIXME markers in code
- Test and build failures
- Gaps found during codebase exploration

## Candidate Features To Do
- [ ] P1: Add schema/version metadata validation command to detect incompatible DBs before API/CLI operations.
- [ ] P1: Add incremental export/import mode with dedupe keys for append-style sync workflows.
- [ ] P2: Add retry/backoff strategy abstraction for Slack API calls (shared for `seed-live` + `provision-slack`).
- [ ] P2: Add optional dry-run planning output for `seed-live` similar to provisioning report shape.
- [ ] P3: Add performance benchmark script + docs for large workspace generation/export baselines.

## Implemented
- [x] 2026-02-08: Fixed CI packaging failure by updating `Makefile` build fallback logic to handle missing `wheel`/`setuptools` safely (`Makefile`).
- [x] 2026-02-08: Fixed Slack channels loader to accept top-level array payloads for `--slack-channels` (`src/slack_workspace_synth/cli.py`, `tests/test_cli_channel_map.py`).
- [x] 2026-02-08: Added fail-fast generation validation for invalid counts, membership bounds, and batch size (`src/slack_workspace_synth/cli.py`, `tests/test_cli_generate_validation.py`).
- [x] 2026-02-08: Added `provision-slack --report` JSON evidence output (`src/slack_workspace_synth/cli.py`, `tests/test_cli_provision_slack.py`).
- [x] 2026-02-08: Updated product memory/docs for behavior changes (`README.md`, `docs/CHANGELOG.md`).
- [x] Verification 2026-02-08: `. .venv/bin/activate && pytest -q tests/test_cli_channel_map.py tests/test_cli_generate_validation.py tests/test_cli_provision_slack.py` (pass, 6 tests).
- [x] Verification 2026-02-08: `. .venv/bin/activate && make check` (pass; lint, mypy, pytest 19 passed, build success).
- [x] Verification 2026-02-08: Local CLI smoke flow (`swsynth generate`, `swsynth stats`, `swsynth channel-map`, `swsynth provision-slack --dry-run --report`) completed with expected outputs.

## Insights
- CI failures from runs `21617680408` through `21618554925` all had the same root cause: `make build` invoked `python -m build --no-isolation` without `wheel` installed in the active venv.
- Slack channel export payloads are not consistently wrapped; accepting top-level arrays removes friction for offline mapping/provisioning.
- Machine-readable run reports improve repeatability and provide evidence for autonomous maintenance loops.

## Notes
- This file is maintained by the autonomous clone loop.

### Auto-discovered Open Checklist Items (2026-02-08)
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] `make check`
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] Update `docs/CHANGELOG.md`
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] Tag release (SemVer)
- /Users/sarvesh/code/slack-workspace-synth/docs/RELEASE.md:- [ ] Create GitHub Release with notes
