"""A2A API —— 跨助理请求端点，给前端的 demo 面板和其它 agent 用。"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from kingdee_console import a2a as a2a_core
from kingdee_console.gateway import default_gateway

router = APIRouter(prefix="/api/a2a", tags=["a2a"])


class A2ARequestInput(BaseModel):
    from_assistant_id: str
    to_assistant_id: str
    verb: str = "query"
    noun: str
    args: dict = {}


@router.post("/request")
async def a2a_request(body: A2ARequestInput) -> dict[str, Any]:
    result = await a2a_core.request(
        body.from_assistant_id, body.to_assistant_id, body.verb, body.noun,
        args=body.args, gateway=default_gateway(),
    )
    return result.to_dict()


@router.get("/log")
async def a2a_log(limit: int = 100) -> list[dict[str, Any]]:
    return a2a_core.audit_log(limit)
