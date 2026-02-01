from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query

from .storage import SQLiteStore

app = FastAPI(title="Slack Workspace Synth")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _resolve_db(db: str | None) -> str:
    resolved = db or os.environ.get("SWSYNTH_DB")
    if not resolved:
        raise HTTPException(status_code=400, detail="db path required")
    return resolved


def _store(db: str | None) -> SQLiteStore:
    return SQLiteStore(_resolve_db(db))


@app.get("/workspaces")
def list_workspaces(
    db: str | None = Query(None, description="Path to SQLite DB"),
) -> list[dict[str, object]]:
    store = _store(db)
    try:
        return store.list_workspaces()
    finally:
        store.close()


@app.get("/workspaces/{workspace_id}")
def get_workspace(
    workspace_id: str, db: str | None = Query(None, description="Path to SQLite DB")
) -> dict[str, object]:
    store = _store(db)
    try:
        workspace = store.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail="workspace not found")
        summary = store.export_summary(workspace_id)
        return summary
    finally:
        store.close()


@app.get("/workspaces/{workspace_id}/users")
def list_users(
    workspace_id: str,
    db: str | None = Query(None, description="Path to SQLite DB"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> list[dict[str, object]]:
    store = _store(db)
    try:
        return store.list_users(workspace_id, limit, offset)
    finally:
        store.close()


@app.get("/workspaces/{workspace_id}/channels")
def list_channels(
    workspace_id: str,
    db: str | None = Query(None, description="Path to SQLite DB"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> list[dict[str, object]]:
    store = _store(db)
    try:
        return store.list_channels(workspace_id, limit, offset)
    finally:
        store.close()


@app.get("/workspaces/{workspace_id}/messages")
def list_messages(
    workspace_id: str,
    db: str | None = Query(None, description="Path to SQLite DB"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> list[dict[str, object]]:
    store = _store(db)
    try:
        return store.list_messages(workspace_id, limit, offset)
    finally:
        store.close()


@app.get("/workspaces/{workspace_id}/files")
def list_files(
    workspace_id: str,
    db: str | None = Query(None, description="Path to SQLite DB"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> list[dict[str, object]]:
    store = _store(db)
    try:
        return store.list_files(workspace_id, limit, offset)
    finally:
        store.close()
