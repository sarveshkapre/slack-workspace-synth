from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query, Response

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
    response: Response,
    db: str | None = Query(None, description="Path to SQLite DB"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    cursor: str | None = Query(
        None, description="Keyset cursor (preferred over offset for large tables)"
    ),
) -> list[dict[str, object]]:
    store = _store(db)
    try:
        if cursor is not None and offset != 0:
            raise HTTPException(status_code=400, detail="Use cursor or offset, not both")
        if cursor is not None:
            try:
                rows, next_cursor = store.list_users_page(workspace_id, limit=limit, cursor=cursor)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from None
            if next_cursor:
                response.headers["X-Next-Cursor"] = next_cursor
            return rows
        return store.list_users(workspace_id, limit, offset)
    finally:
        store.close()


@app.get("/workspaces/{workspace_id}/channels")
def list_channels(
    workspace_id: str,
    response: Response,
    db: str | None = Query(None, description="Path to SQLite DB"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    channel_type: str | None = Query(None, description="Filter by channel type"),
    cursor: str | None = Query(
        None, description="Keyset cursor (preferred over offset for large tables)"
    ),
) -> list[dict[str, object]]:
    store = _store(db)
    try:
        if cursor is not None and offset != 0:
            raise HTTPException(status_code=400, detail="Use cursor or offset, not both")
        if cursor is not None:
            try:
                rows, next_cursor = store.list_channels_page(
                    workspace_id, limit=limit, cursor=cursor, channel_type=channel_type
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from None
            if next_cursor:
                response.headers["X-Next-Cursor"] = next_cursor
            return rows
        return store.list_channels(workspace_id, limit, offset, channel_type=channel_type)
    finally:
        store.close()


@app.get("/workspaces/{workspace_id}/channel-members")
def list_channel_members(
    workspace_id: str,
    response: Response,
    db: str | None = Query(None, description="Path to SQLite DB"),
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    channel_id: str | None = Query(None, description="Filter by channel id"),
    cursor: str | None = Query(
        None, description="Keyset cursor (preferred over offset for large tables)"
    ),
) -> list[dict[str, object]]:
    store = _store(db)
    try:
        if cursor is not None and offset != 0:
            raise HTTPException(status_code=400, detail="Use cursor or offset, not both")
        if cursor is not None:
            try:
                rows, next_cursor = store.list_channel_members_page(
                    workspace_id, limit=limit, cursor=cursor, channel_id=channel_id
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from None
            if next_cursor:
                response.headers["X-Next-Cursor"] = next_cursor
            return rows
        return store.list_channel_members(
            workspace_id, limit, offset, channel_id=channel_id
        )
    finally:
        store.close()


@app.get("/workspaces/{workspace_id}/messages")
def list_messages(
    workspace_id: str,
    response: Response,
    db: str | None = Query(None, description="Path to SQLite DB"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    cursor: str | None = Query(
        None, description="Keyset cursor (preferred over offset for large tables)"
    ),
    channel_id: str | None = Query(None),
    user_id: str | None = Query(None),
    before_ts: int | None = Query(None, ge=0),
    after_ts: int | None = Query(None, ge=0),
) -> list[dict[str, object]]:
    store = _store(db)
    try:
        use_keyset = cursor is not None or any(
            v is not None for v in (channel_id, user_id, before_ts, after_ts)
        )
        if use_keyset and offset != 0:
            raise HTTPException(status_code=400, detail="Use cursor or offset, not both")
        if use_keyset:
            try:
                rows, next_cursor = store.list_messages_page(
                    workspace_id,
                    limit=limit,
                    cursor=cursor,
                    channel_id=channel_id,
                    user_id=user_id,
                    before_ts=before_ts,
                    after_ts=after_ts,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from None
            if next_cursor:
                response.headers["X-Next-Cursor"] = next_cursor
            return rows
        return store.list_messages(workspace_id, limit, offset)
    finally:
        store.close()


@app.get("/workspaces/{workspace_id}/files")
def list_files(
    workspace_id: str,
    response: Response,
    db: str | None = Query(None, description="Path to SQLite DB"),
    limit: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    cursor: str | None = Query(
        None, description="Keyset cursor (preferred over offset for large tables)"
    ),
    channel_id: str | None = Query(None),
    user_id: str | None = Query(None),
    before_ts: int | None = Query(None, ge=0, description="Filter by created_ts < before_ts"),
    after_ts: int | None = Query(None, ge=0, description="Filter by created_ts > after_ts"),
) -> list[dict[str, object]]:
    store = _store(db)
    try:
        use_keyset = cursor is not None or any(
            v is not None for v in (channel_id, user_id, before_ts, after_ts)
        )
        if use_keyset and offset != 0:
            raise HTTPException(status_code=400, detail="Use cursor or offset, not both")
        if use_keyset:
            try:
                rows, next_cursor = store.list_files_page(
                    workspace_id,
                    limit=limit,
                    cursor=cursor,
                    channel_id=channel_id,
                    user_id=user_id,
                    before_ts=before_ts,
                    after_ts=after_ts,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from None
            if next_cursor:
                response.headers["X-Next-Cursor"] = next_cursor
            return rows
        return store.list_files(workspace_id, limit, offset)
    finally:
        store.close()
