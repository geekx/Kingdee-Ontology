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


def test_graph_exposes_verbs_and_categories_for_the_editor(seeded):
    c = TestClient(create_app())
    body = c.get("/api/ontology/graph").json()
    assert {v["name"] for v in body["verbs"]} >= {"query", "save", "submit", "audit", "push"}
    assert set(body["categories"]) == {"bill", "master_data", "view", "system"}


def test_add_noun_creates_a_new_node_visible_in_next_graph_fetch(seeded):
    c = TestClient(create_app())
    before = c.get("/api/ontology/graph").json()

    r = c.post("/api/ontology/nouns", json={
        "form_id": "PAEZ_CustomInvoice", "zh": "客户开票申请单", "category": "bill",
        "allowed_verbs": ["query", "read", "save", "submit"],
        "alias": ["开票申请", "开票单"], "default_fields": "FID,FBillNo,FDate",
    })
    assert r.status_code == 200
    assert r.json() == {
        "form_id": "PAEZ_CustomInvoice", "zh": "客户开票申请单", "category": "bill",
        "allowed_verbs": ["query", "read", "save", "submit"],
        "alias": ["开票申请", "开票单"], "default_fields": "FID,FBillNo,FDate",
    }

    after = c.get("/api/ontology/graph").json()
    assert len(after["nodes"]) == len(before["nodes"]) + 1
    node = next(n for n in after["nodes"] if n["id"] == "PAEZ_CustomInvoice")
    assert node["label"] == "客户开票申请单"
    assert node["category"] == "bill"
    assert node["color"]["label"] == "单据"
    assert node["allowed_verbs"] == ["query", "read", "save", "submit"]


def test_add_noun_resolvable_by_alias_afterwards(seeded):
    """新增的名词不只是图上多一个点——Dispatcher 真的认得它，能用别名查。"""
    c = TestClient(create_app())
    c.post("/api/ontology/nouns", json={
        "form_id": "PAEZ_CustomInvoice", "zh": "客户开票申请单", "category": "bill",
        "allowed_verbs": ["query"], "alias": ["开票单"],
    })
    r = c.post("/api/tools/kd_query/call", json={"args": {"params": {"noun": "开票单"}}})
    assert r.status_code == 200
    assert r.json()["noun"] == "PAEZ_CustomInvoice"


def test_add_noun_overwrites_same_form_id(seeded):
    c = TestClient(create_app())
    c.post("/api/ontology/nouns", json={
        "form_id": "PAEZ_X", "zh": "第一版", "category": "bill", "allowed_verbs": ["query"],
    })
    c.post("/api/ontology/nouns", json={
        "form_id": "PAEZ_X", "zh": "改过的", "category": "view", "allowed_verbs": ["query", "read"],
    })

    after = c.get("/api/ontology/graph").json()
    matches = [n for n in after["nodes"] if n["id"] == "PAEZ_X"]
    assert len(matches) == 1
    assert matches[0]["label"] == "改过的"
    assert matches[0]["category"] == "view"


def test_add_noun_rejects_invalid_category(seeded):
    c = TestClient(create_app())
    r = c.post("/api/ontology/nouns",
              json={"form_id": "X", "zh": "x", "category": "不存在的类别", "allowed_verbs": ["query"]})
    assert r.status_code == 400


def test_add_noun_rejects_unknown_verb(seeded):
    c = TestClient(create_app())
    r = c.post("/api/ontology/nouns",
              json={"form_id": "X", "zh": "x", "category": "bill", "allowed_verbs": ["飞起来"]})
    assert r.status_code == 400


def test_add_noun_rejects_empty_verbs(seeded):
    c = TestClient(create_app())
    r = c.post("/api/ontology/nouns",
              json={"form_id": "X", "zh": "x", "category": "bill", "allowed_verbs": []})
    assert r.status_code == 400


def test_add_noun_rejects_blank_form_id_or_zh(seeded):
    c = TestClient(create_app())
    r1 = c.post("/api/ontology/nouns",
               json={"form_id": "  ", "zh": "x", "category": "bill", "allowed_verbs": ["query"]})
    assert r1.status_code == 400
    r2 = c.post("/api/ontology/nouns",
               json={"form_id": "X", "zh": "  ", "category": "bill", "allowed_verbs": ["query"]})
    assert r2.status_code == 400
