"""对象卡片 API ——节点编辑器"看着有点单薄"之后，给节点加上属性/状态轨道/
动作可用性，复用 base/objects.py 的 ObjectModel，不重新判断一遍。
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="需要 pip install -e \".[console]\" 才能测 HTTP 层")

from fastapi.testclient import TestClient  # noqa: E402

from kingdee_console.app import create_app  # noqa: E402


def test_card_without_state_returns_type_level_info(seeded):
    c = TestClient(create_app())
    body = c.get("/api/ontology/nouns/SAL_SaleOrder/card").json()

    assert body["object_type"] == "SAL_SaleOrder"
    assert body["zh"] == "销售订单"
    assert body["is_instance"] is False
    assert body["selected_state"] is None
    assert body["state"] is None
    # 属性来自 default_fields，至少带上单据编号
    assert any(p["name"] == "FBillNo" for p in body["properties"])
    # 状态轨道列出该类单据所有可能状态，供前端做模拟点击
    codes = {s["code"] for s in body["states"]}
    assert "Z:暂存" in codes
    assert "C:已审核" in codes
    # 没点具体状态时，所有写动作都应标为"未核实"（判断层不把"不知道"读成"可以"）
    submit = next(a for a in body["actions"] if a["verb"] == "submit")
    assert submit["unverified"] is True


def test_card_with_draft_state_enables_submit_but_not_audit(seeded):
    c = TestClient(create_app())
    body = c.get("/api/ontology/nouns/SAL_SaleOrder/card", params={"state": "Z:暂存"}).json()

    assert body["selected_state"] == "Z:暂存"
    assert body["state_zh"] == "暂存"
    submit = next(a for a in body["actions"] if a["verb"] == "submit")
    assert submit["enabled"] is True
    audit = next(a for a in body["actions"] if a["verb"] == "audit")
    assert audit["enabled"] is False
    assert audit["reason"]


def test_card_with_reviewed_state_enables_audited_only_actions(seeded):
    c = TestClient(create_app())
    body = c.get("/api/ontology/nouns/SAL_SaleOrder/card", params={"state": "C:已审核"}).json()

    audit = next(a for a in body["actions"] if a["verb"] == "audit")
    assert audit["enabled"] is False
    void = next(a for a in body["actions"] if a["verb"] == "void")
    assert void["enabled"] is True
    assert void["destructive"] is True
    assert void["needs_confirmation"] is True


def test_card_exposes_push_links_with_verified_flag(seeded):
    c = TestClient(create_app())
    body = c.get("/api/ontology/nouns/SAL_SaleOrder/card").json()
    outgoing = [l for l in body["links"] if l["direction"] == "outgoing"]
    assert any(l["target_type"] == "SAL_OUTSTOCK" for l in outgoing)
    assert all("verified" in l for l in outgoing)


def test_card_rejects_unknown_state(seeded):
    c = TestClient(create_app())
    r = c.get("/api/ontology/nouns/SAL_SaleOrder/card", params={"state": "不存在的状态"})
    assert r.status_code == 400


def test_card_rejects_unknown_noun(seeded):
    c = TestClient(create_app())
    r = c.get("/api/ontology/nouns/不存在的名词/card")
    assert r.status_code == 400


def test_card_reflects_custom_noun_added_via_editor(seeded):
    """编辑器新增的名词也能开出对象卡片——不是只有底座登记的那些。"""
    c = TestClient(create_app())
    c.post("/api/ontology/nouns", json={
        "form_id": "PAEZ_CustomInvoice", "zh": "客户开票申请单", "category": "bill",
        "allowed_verbs": ["query", "read", "save", "submit"],
    })
    body = c.get("/api/ontology/nouns/PAEZ_CustomInvoice/card").json()
    assert body["zh"] == "客户开票申请单"
    assert any(a["verb"] == "submit" for a in body["actions"])
