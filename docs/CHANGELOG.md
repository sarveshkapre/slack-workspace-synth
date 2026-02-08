# CHANGELOG

## Unreleased
- Fixed CI `make check` failures by making `make build` fall back to isolated builds when the active venv
  is missing `setuptools`/`wheel`.
- Fixed Slack channel payload parsing for `channel-map`/`seed-live`/`provision-slack` so
  `--slack-channels` now accepts top-level JSON arrays in addition to object wrappers.
- Added validation guards for `swsynth generate` to fail fast on invalid counts, batch size, and membership
  bounds.
- Added `--report` to `swsynth provision-slack` to emit machine-readable provisioning stats.
- Added `docs/ENTERPRISE_GRID_SEEDING.md` with a practical plan for Enterprise Grid seeding using Entra SCIM,
  per-user OAuth (for true user-authored messages), and optional bulk history import.
- Added `swsynth oauth-pack` to generate per-user Slack OAuth URLs for clickops token collection.
- Added `swsynth seed-import` to generate a Slack export-style import bundle.
- Added `swsynth seed-live` to post messages to Slack using per-user tokens.
- Added `swsynth oauth-callback` to exchange OAuth codes for per-user tokens.
- Added `swsynth channel-map` to generate a synthetic-to-Slack channel mapping.
- Extended `swsynth seed-live` to auto-generate the channel map when none is provided.
- Added `swsynth provision-slack` to create channels and invite members in Slack.

## v0.1.2
- Added DM/MPDM channel generation plus a channel member table.
- Added `channel_type` on channels with optional filtering and type counts in summary exports.
- Added `channel-members` API endpoint and JSONL import/export support.

## v0.1.1
- Added `swsynth export-jsonl` for streaming JSONL exports (optionally gzipped).
- Added cursor-based pagination for API `users`, `channels`, `messages`, and `files` with `X-Next-Cursor`.
- Added `swsynth stats` for quick workspace counts.
- Added per-workspace generation metadata stored in SQLite and included in summary exports (`meta`).
- Added `swsynth import-jsonl` to load JSONL exports back into SQLite.

## v0.1.0
- Initial MVP: generator, SQLite storage, CLI, FastAPI read-only API, plugin hooks.
