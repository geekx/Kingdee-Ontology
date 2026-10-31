"""能力目录上色：类别→颜色映射正确，能从真实 dispatch 结果反推出标签。"""
from __future__ import annotations

import asyncio

from kingdee_console.catalog import (
    catalog_summary, color_for_category, full_catalog, tag_for, tags_from_dispatch_result,
)
from kingdee_console.gateway import McpGateway


def test_color_for_known_categories_is_distinct():
    colors = {color_for_category(c)["bg"] for c in ("bill", "master_data", "view", "system")}
    assert len(colors) == 4, "四个类别的底色必须互不相同，否则 UI 上分不清"


def test_color_for_unknown_category_falls_back():
    assert color_for_category("不存在的类别") == color_for_category("也不存在")


def test_full_catalog_covers_every_noun_verb_pair(seeded):
    gw = McpGateway()
    entries = full_catalog(gw.ontology)
    assert len(entries) == catalog_summary(gw.ontology)["total_capabilities"]
    # STK_Inventory 在注册表里只允许 query，颜色必须是 view 类别的颜色
    inv_entries = [e for e in entries if e.noun == "STK_Inventory"]
    assert {e.verb for e in inv_entries} == {"query"}
    assert inv_entries[0].color == color_for_category("view")


def test_tag_for_unknown_verb_or_noun_returns_none(seeded):
    gw = McpGateway()
    assert tag_for(gw.ontology, "query", "不存在的名词") is None
    assert tag_for(gw.ontology, "不存在的动词", "STK_Inventory") is None


def test_tags_from_dispatch_result_single_noun(seeded):
    gw = McpGateway()

    async def run():
        return await gw.call_tool("kd_query", {"params": {"noun": "库存"}})

    result = asyncio.run(run())
    tags = tags_from_dispatch_result(gw.ontology, "kd_query", result)
    assert len(tags) == 1
    t = tags[0]
    assert t.noun == "STK_Inventory" and t.verb == "query" and t.kind == "read"
    assert t.destructive is False
    assert t.color == color_for_category("view")


def test_tags_from_dispatch_result_multi_noun_query(seeded):
    gw = McpGateway()

    async def run():
        return await gw.call_tool("kd_query", {"params": {"noun": "库存,销售订单"}})

    result = asyncio.run(run())
    tags = tags_from_dispatch_result(gw.ontology, "kd_query", result)
    nouns = {t.noun for t in tags}
    assert nouns == {"STK_Inventory", "SAL_SaleOrder"}
