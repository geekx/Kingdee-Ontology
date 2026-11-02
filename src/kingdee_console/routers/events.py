"""工具调用事件流 —— Ontology 节点流向动效订阅这个。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from kingdee_console.events import bus

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/recent")
async def recent(limit: int = 50) -> list[dict[str, Any]]:
    return [e.to_dict() for e in bus.history[-limit:]]


@router.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = bus.subscribe()
    try:
        # 先补发最近的历史，前端一连上就能看到图已经"活过"，不是一片死寂
        for event in bus.history[-20:]:
            await websocket.send_json(event.to_dict())
        while True:
            event = await queue.get()
            await websocket.send_json(event.to_dict())
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(queue)
