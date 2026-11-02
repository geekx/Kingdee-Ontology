"""Ontology 图谱 API —— 节点编辑器 + 流向监测前端读的就是这个。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kingdee_console import ontology_editor
from kingdee_console.catalog import color_for_category
from kingdee_console.gateway import default_gateway

router = APIRouter(prefix="/api/ontology", tags=["ontology"])


@router.get("/graph")
async def graph() -> dict[str, Any]:
    gw = default_gateway()
    o = gw.ontology
    nodes = [
        {"id": n.form_id, "label": n.zh, "category": n.category,
         "color": color_for_category(n.category), "allowed_verbs": sorted(n.allowed_verbs)}
        for n in o.nouns.values()
    ]
    edges = [
        {"id": f"{link['from']}->{link['to']}", "source": link["from"], "target": link["to"],
         "label": link.get("zh", ""), "verified": link.get("verified", "")}
        for link in o.links
    ]
    return {
        "nodes": nodes, "edges": edges,
        "active_profile": ontology_editor.active_profile_name(gw.demo),
    }


class AddLinkInput(BaseModel):
    source: str
    target: str
    zh: str = ""


@router.post("/links")
async def add_link(body: AddLinkInput) -> dict[str, Any]:
    """新增一条下推关系，写进"当前活跃 profile"的覆盖层——不碰底座 registry.yml。"""
    gw = default_gateway()
    o = gw.ontology
    try:
        s = o.resolve_noun(body.source)
        t = o.resolve_noun(body.target)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    profile = ontology_editor.active_profile_name(gw.demo)
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="没有可写入的 profile——真实模式下请先设 KINGDEE_TENANT 指到一个租户配置",
        )
    zh = body.zh or f"{s.zh}→{t.zh}"
    entry = ontology_editor.add_link(profile, s.form_id, t.form_id, zh)

    if gw.demo:
        from kingdee_console import demo_data
        demo_data.reset_dispatcher()

    return entry
