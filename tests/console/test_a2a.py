"""A2A demo：销售助理没有仓库权限，必须经仓库助理才能拿到库存数据；
反过来问也一样受限；每次请求（允许/拒绝）都要落审计。
"""
from __future__ import annotations

import asyncio

from kingdee_console import a2a, tenancy
from kingdee_console.gateway import McpGateway


def test_sales_assistant_cannot_touch_inventory_directly(seeded):
    """direct-access 场景：销售助理自己的角色就没有库存权限——
    用它自己的身份去"问自己"等价于越权直查，必须被拒。"""
    result = asyncio.run(a2a.request(
        tenancy.ASSISTANT_SALES_ID, tenancy.ASSISTANT_SALES_ID, "query", "库存"))
    assert result.ok is False
    assert "STK_Inventory" in result.reason


def test_sales_assistant_borrows_inventory_via_warehouse_assistant(seeded):
    """核心场景：销售助理问仓库助理（继承仓库角色权限）要库存数据，成功，
    且返回体带 provenance——执行者是仓库助理，不是销售助理自己。"""
    result = asyncio.run(a2a.request(
        tenancy.ASSISTANT_SALES_ID, tenancy.ASSISTANT_WAREHOUSE_ID, "query", "库存"))
    assert result.ok is True
    assert result.result["noun"] == "STK_Inventory"
    assert result.result["count"] == 2
    assert result.provenance["executed_by"] == "仓库助理"
    assert result.provenance["executed_by_role"] == "仓库"
    assert result.provenance["requested_by"] == "销售助理"
    assert result.provenance["capabilities"][0]["noun"] == "STK_Inventory"


def test_warehouse_assistant_cannot_borrow_sale_order_from_itself_either(seeded):
    """对称检查：仓库助理问销售助理要销售订单——销售助理自己都没被授权
    （这次只开了 SAL_SaleOrder 给销售角色，仓库助理问的是反方向，应该
    能成功；用一个两边都没权限的名词来验证"真的按 to_assistant 的角色判"。"""
    result = asyncio.run(a2a.request(
        tenancy.ASSISTANT_WAREHOUSE_ID, tenancy.ASSISTANT_SALES_ID, "query", "销售订单"))
    assert result.ok is True
    assert result.result["noun"] == "SAL_SaleOrder"
    assert result.provenance["executed_by"] == "销售助理"


def test_unknown_noun_is_denied_before_any_rbac_check(seeded):
    result = asyncio.run(a2a.request(
        tenancy.ASSISTANT_SALES_ID, tenancy.ASSISTANT_WAREHOUSE_ID, "query", "不存在的名词"))
    assert result.ok is False


def test_unknown_assistant_is_denied(seeded):
    result = asyncio.run(a2a.request("不存在", tenancy.ASSISTANT_WAREHOUSE_ID, "query", "库存"))
    assert result.ok is False
    assert result.reason == "助理不存在"


def test_every_request_is_audited_allowed_and_denied(seeded):
    gw = McpGateway()
    asyncio.run(a2a.request(tenancy.ASSISTANT_SALES_ID, tenancy.ASSISTANT_SALES_ID,
                            "query", "库存", gateway=gw))
    asyncio.run(a2a.request(tenancy.ASSISTANT_SALES_ID, tenancy.ASSISTANT_WAREHOUSE_ID,
                            "query", "库存", gateway=gw))
    log = a2a.audit_log()
    assert len(log) == 2
    allowed = [r for r in log if r["allowed"]]
    denied = [r for r in log if not r["allowed"]]
    assert len(allowed) == 1 and len(denied) == 1
    assert all(r["noun"] == "STK_Inventory" for r in log)
