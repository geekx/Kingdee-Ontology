"""A2A API —— 跨助理请求端点，给前端的 demo 面板和其它 agent 用。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from kingdee_console import a2a as a2a_core

router = APIRouter(prefix="/api/a2a", tags=["a2a"])


class A2ARequestInput(BaseModel):
    from_assistant_id: str
    to_assistant_id: str
    verb: str = "query"
    noun: str
    args: dict = {}


@router.post("/request")
async def a2a_request(body: A2ARequestInput) -> dict[str, Any]:
    # 不传 gateway——让 a2a.request() 自己按 to_assistant 所属租户从
    # tenant_pool 里挑网关；固定传 default_gateway() 会把"按租户路由"
    # 这件事架空（永远用同一个共享连接，不管目标助理在哪个账套）。
    result = await a2a_core.request(
        body.from_assistant_id, body.to_assistant_id, body.verb, body.noun, args=body.args,
    )
    return result.to_dict()


@router.get("/log")
async def a2a_log(limit: int = 100) -> list[dict[str, Any]]:
    return a2a_core.audit_log(limit)
