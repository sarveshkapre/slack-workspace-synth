# PLAN

## Summary
Slack Workspace Synth generates a synthetic Slack-like workspace (users, channels, messages, files) for demos, load testing, or analytics prototyping. It provides a deterministic generator, a plug-in hook system, a SQLite-backed store, and an optional FastAPI server for querying generated data.

## Goals (MVP)
- Generate a workspace with ~2,000 users, channels, messages, and files deterministically from a seed.
- Store generated data in a local SQLite database.
- Provide a CLI for generation and exporting.
- Provide a simple FastAPI server with read-only endpoints.
- Offer a plug-in hook API to customize entities during generation.

## Non-goals (MVP)
- No authentication or multi-tenant access control.
- No real Slack API compatibility.
- No external storage (S3, Postgres) or distributed generation.

## Stack
- Python 3.11
- FastAPI + Uvicorn (optional API)
- SQLite (local persistence)
- Faker (synthetic data)
- Typer (CLI)
- Ruff + Mypy + Pytest

## Architecture
- `generator.py`: deterministic entity generator
- `plugins.py`: hook registry + plugin loading
- `storage.py`: SQLite schema + write/read helpers
- `api.py`: FastAPI read API
- `cli.py`: generation + serving commands

## Data model (MVP)
- Workspace
- User
- Channel
- Message
- File

## Milestones
1. Scaffold repo + docs + CI + Makefile.
2. Implement generator + SQLite store.
3. Implement CLI + plugin hooks.
4. Implement FastAPI read-only API.
5. Tests + lint/typecheck/build + documentation.

## Shipped (most recent)
- Cursor-based pagination for `users`, `channels`, `messages`, and `files` (keyset pagination with `X-Next-Cursor` header).
- CLI export: `swsynth export-jsonl` for streaming JSONL exports (optionally gzipped).
- CLI stats: `swsynth stats` for quick workspace counts.

## Risks
- Large synthetic datasets may exceed memory; mitigate with streaming writes.
- SQLite write performance; mitigate via batching + pragmas.
- Unbounded plugin behavior; mitigate with explicit hook boundaries.
