"""Dashboard API —— 能力目录、租户/角色/助理管理、直接调用（旁路 LLM）。

"保留本身直接访问的能力"：POST /tools/{name}/call 不经过 intent.py 的
LLM 循环，直接走同一个 gateway——Dashboard 的"能力浏览器"面板、以及
程序化调用都走这条路。
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kingdee_console import a2a, tenancy
from kingdee_console.catalog import catalog_summary, full_catalog
from kingdee_console.gateway import default_gateway

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/catalog")
async def get_catalog() -> dict[str, Any]:
    gw = default_gateway()
    return {"summary": catalog_summary(gw.ontology),
            "entries": [e.to_dict() for e in full_catalog(gw.ontology)],
            "demo_mode": gw.demo}


@router.get("/tools")
async def get_tools() -> dict[str, Any]:
    gw = default_gateway()
    tools = await gw.list_tools()
    return {"tools": [{"name": t.name, "description": t.description,
                       "input_schema": t.input_schema} for t in tools],
            "demo_mode": gw.demo}


class DirectCallInput(BaseModel):
    args: dict = {}


@router.post("/tools/{name}/call")
async def call_tool_directly(name: str, body: DirectCallInput) -> dict[str, Any]:
    gw = default_gateway()
    try:
        return await gw.call_tool(name, body.args)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{type(e).__name__}: {e}")


@router.get("/tenants")
async def get_tenants() -> list[dict[str, Any]]:
    return [t.to_dict() for t in tenancy.list_tenants()]


@router.get("/roles")
async def get_roles() -> list[dict[str, Any]]:
    return [r.to_dict() for r in tenancy.list_roles()]


@router.get("/assistants")
async def get_assistants() -> list[dict[str, Any]]:
    return [a.to_dict() for a in tenancy.list_assistants()]


class CreateTenantInput(BaseModel):
    name: str
    profile: str = ""


@router.post("/tenants")
async def create_tenant(body: CreateTenantInput) -> dict[str, Any]:
    return tenancy.create_tenant(body.name, body.profile).to_dict()


class CreateRoleInput(BaseModel):
    name: str
    allowed_nouns: list[str] = []


@router.post("/roles")
async def create_role(body: CreateRoleInput) -> dict[str, Any]:
    return tenancy.create_role(body.name, body.allowed_nouns).to_dict()


class CreateAssistantInput(BaseModel):
    name: str
    tenant_id: str
    role_id: str


@router.post("/assistants")
async def create_assistant(body: CreateAssistantInput) -> dict[str, Any]:
    if tenancy.get_tenant(body.tenant_id) is None:
        raise HTTPException(status_code=404, detail="租户不存在")
    if tenancy.get_role(body.role_id) is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return tenancy.create_assistant(body.name, body.tenant_id, body.role_id).to_dict()


@router.get("/a2a/log")
async def get_a2a_log(limit: int = 100) -> list[dict[str, Any]]:
    return a2a.audit_log(limit)
