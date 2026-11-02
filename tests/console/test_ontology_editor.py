"""Ontology 图谱 API + 节点编辑器：新增下推关系写进 profile 覆盖层，立即可见。

需要 pip install -e ".[console]"——见 test_api.py 顶部的说明。
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="需要 pip install -e \".[console]\" 才能测 HTTP 层")

from fastapi.testclient import TestClient  # noqa: E402

from kingdee_console.app import create_app  # noqa: E402


def test_graph_lists_all_nouns_and_base_links(seeded):
    c = TestClient(create_app())
    body = c.get("/api/ontology/graph").json()
    assert len(body["nodes"]) >= 80
    assert len(body["edges"]) == 9           # registry.yml 里登记的下推关系数
    assert body["active_profile"] == "console-demo"
    inv = next(n for n in body["nodes"] if n["id"] == "STK_Inventory")
    assert inv["category"] == "view"
    assert inv["color"]["label"] == "视图/查询"


def test_add_link_shows_up_in_next_graph_fetch(seeded):
    c = TestClient(create_app())
    before = c.get("/api/ontology/graph").json()

    r = c.post("/api/ontology/links",
              json={"source": "库存", "target": "销售订单", "zh": "演示自定义下推"})
    assert r.status_code == 200
    assert r.json() == {"from": "STK_Inventory", "to": "SAL_SaleOrder",
                        "zh": "演示自定义下推", "verified": "confirmed"}

    after = c.get("/api/ontology/graph").json()
    assert len(after["edges"]) == len(before["edges"]) + 1
    new_edge = next(e for e in after["edges"] if e["id"] == "STK_Inventory->SAL_SaleOrder")
    assert new_edge["label"] == "演示自定义下推"


def test_add_link_overwrites_same_from_to_pair(seeded):
    c = TestClient(create_app())
    c.post("/api/ontology/links", json={"source": "库存", "target": "销售订单", "zh": "第一次"})
    c.post("/api/ontology/links", json={"source": "库存", "target": "销售订单", "zh": "改过的"})

    after = c.get("/api/ontology/graph").json()
    matches = [e for e in after["edges"] if e["id"] == "STK_Inventory->SAL_SaleOrder"]
    assert len(matches) == 1
    assert matches[0]["label"] == "改过的"


def test_add_link_rejects_unknown_noun(seeded):
    c = TestClient(create_app())
    r = c.post("/api/ontology/links", json={"source": "不存在的名词", "target": "销售订单"})
    assert r.status_code == 400
