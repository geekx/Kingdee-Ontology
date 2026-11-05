"""Ontology 图谱 API —— 节点编辑器 + 流向监测前端读的就是这个。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kingdee_console import ontology_editor
from kingdee_console.catalog import color_for_category
from kingdee_console.gateway import default_gateway
from kingdee_ontology.base.objects import ObjectModel
from kingdee_ontology.base.ontology import OntologyError

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
    # 名词编辑器要知道合法的动词名和类别——跟 kd_describe(what='verbs') 是
    # 同一份数据，这里顺手带出来，前端不用再敲一遍。
    verbs = [{"name": v.name, "zh": v.zh, "kind": v.kind} for v in o.verbs.values()]
    return {
        "nodes": nodes, "edges": edges, "verbs": sorted(verbs, key=lambda v: v["name"]),
        "categories": sorted(ontology_editor.VALID_CATEGORIES),
        "active_profile": ontology_editor.active_profile_name(gw.demo),
    }


def _active_profile_or_400(gw) -> str:
    profile = ontology_editor.active_profile_name(gw.demo)
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="没有可写入的 profile——真实模式下请先设 KINGDEE_TENANT 指到一个租户配置",
        )
    return profile


def _refresh_after_edit(gw) -> None:
    """编辑器写完 profile.yml 后调这个——demo 模式下缓存的 Dispatcher 还
    攥着旧的 Ontology 对象，不重建看不到新写的内容（真实模式下
    gateway.ontology 本来就是现读现 load()，不需要额外处理）。"""
    if gw.demo:
        from kingdee_console import demo_data
        demo_data.reset_dispatcher()


@router.get("/nouns/{form_id}/card")
async def noun_card(form_id: str, state: str = "") -> dict[str, Any]:
    """对象卡片：属性 + 状态轨道 + 此刻（模拟某状态下）能做什么。

    不传 state 时按类型本身的默认判断（未知状态）给可用性；传了就是
    "点一个状态码，看这时候哪些动作亮/灰、为什么"——跟 Explorer 的状态轨道
    模拟一样，只是算的是这台正在跑的 Ontology（含控制台编辑器新增的名词），
    判断逻辑复用 ObjectModel/ActionType.availability，不重新写一遍。
    """
    gw = default_gateway()
    o = gw.ontology
    m = ObjectModel(o)
    try:
        card = m.card(form_id)
    except OntologyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ot = m.object_type(form_id)
    picked = state or None
    if picked is not None and picked not in ot.states:
        raise HTTPException(
            status_code=400,
            detail=f"{form_id} 没有状态 {picked!r}，可选：{ot.states}",
        )
    if picked is not None:
        card["actions"] = [{**a.to_dict(), **a.availability(picked)} for a in ot.actions]
        card["state"] = picked
        card["state_zh"] = (o.states.get(picked) or {}).get("zh")

    card["states"] = [{"code": s, "zh": (o.states.get(s) or {}).get("zh", s)} for s in ot.states]
    card["selected_state"] = picked
    return card


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

    profile = _active_profile_or_400(gw)
    zh = body.zh or f"{s.zh}→{t.zh}"
    entry = ontology_editor.add_link(profile, s.form_id, t.form_id, zh)
    _refresh_after_edit(gw)
    return entry


class AddNounInput(BaseModel):
    form_id: str
    zh: str
    category: str
    allowed_verbs: list[str]
    alias: list[str] = []
    default_fields: str = ""


@router.post("/nouns")
async def add_noun(body: AddNounInput) -> dict[str, Any]:
    """新增（或改写）一个自定义名词，写进"当前活跃 profile"的覆盖层——
    不碰底座 registry.yml。form_id 若已在底座/当前 profile 里存在，
    这次提交的字段会覆盖同名字段，其它字段保留原值（跟 Ontology._merge()
    的合并规则一致，对应 profile 系统"只改一两个字段"的设计用途）。
    """
    form_id = body.form_id.strip()
    zh = body.zh.strip()
    if not form_id or not zh:
        raise HTTPException(status_code=400, detail="form_id 和 zh 都不能为空")

    if body.category not in ontology_editor.VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"category 必须是 {sorted(ontology_editor.VALID_CATEGORIES)} 之一，收到 {body.category!r}",
        )

    gw = default_gateway()
    o = gw.ontology
    unknown_verbs = [v for v in body.allowed_verbs if v not in o.verbs]
    if not body.allowed_verbs:
        raise HTTPException(status_code=400, detail="allowed_verbs 不能为空，至少选一个动词")
    if unknown_verbs:
        raise HTTPException(
            status_code=400,
            detail=f"未知动词 {unknown_verbs}，可用动词：{sorted(o.verbs)}",
        )

    profile = _active_profile_or_400(gw)
    entry = ontology_editor.add_noun(
        profile, form_id, zh, body.category, body.allowed_verbs,
        alias=body.alias, default_fields=body.default_fields,
    )
    _refresh_after_edit(gw)
    return entry
