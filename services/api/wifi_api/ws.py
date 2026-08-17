"""WebSocket endpoint: snapshot recovery + live stream + control messages."""

from __future__ import annotations

import contextlib

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from .stream import get_hub

router = APIRouter(tags=["stream"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str | None = Query(default=None),
    last_sequence: int | None = Query(default=None, ge=0),
) -> None:
    with contextlib.suppress(WebSocketDisconnect):
        await get_hub().connect(websocket, last_sequence=last_sequence)
