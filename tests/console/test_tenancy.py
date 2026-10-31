"""租户/角色/助理：RBAC 只收紧不放宽，种子数据幂等。"""
from __future__ import annotations

from kingdee_console import tenancy


def test_ensure_seed_data_is_idempotent(console_database):
    tenancy.ensure_seed_data()
    tenancy.ensure_seed_data()
    assert len(tenancy.list_tenants()) == 1
    assert len(tenancy.list_assistants()) == 2


def test_role_can_only_checks_allowlist(seeded):
    sales = tenancy.get_role(tenancy.ROLE_SALES_ID)
    warehouse = tenancy.get_role(tenancy.ROLE_WAREHOUSE_ID)
    assert sales.can("SAL_SaleOrder") is True
    assert sales.can("STK_Inventory") is False
    assert warehouse.can("STK_Inventory") is True
    assert warehouse.can("SAL_SaleOrder") is False


def test_create_tenant_role_assistant_roundtrip(console_database):
    t = tenancy.create_tenant("另一个租户", profile="example-tenant")
    r = tenancy.create_role("财务", ["AR_Receivable"])
    a = tenancy.create_assistant("财务助理", t.id, r.id)

    assert tenancy.get_tenant(t.id).name == "另一个租户"
    assert tenancy.get_role(r.id).can("AR_Receivable") is True
    fetched = tenancy.get_assistant(a.id)
    assert fetched.tenant_id == t.id and fetched.role_id == r.id


def test_missing_entities_resolve_to_none(console_database):
    assert tenancy.get_tenant("不存在") is None
    assert tenancy.get_role("不存在") is None
    assert tenancy.get_assistant("不存在") is None
