"""演示模式的数据源 —— 不连真账套，但走的是真实的 Ontology/Dispatcher 代码路径。

不另起一套假 schema：11 个 kd_* 工具的名字、描述、inputSchema 仍然是
base/server.py 里真实定义的那些；只换最后一跳的传输层——把
Dispatcher 工厂 `_d()` 换成这里的版本，注入 FakeTransport + 预置的
示例行，代替真的金蝶 HTTP 请求。跟 tests/ 目录测基座用的是同一种手法
（见 tests/test_query_parity.py 等用到的 FakeTransport）。

这样一来，kd_describe/kd_query/kd_act 的分发、前置校验、过程审计、
contract 契约这些逻辑全部是真的在跑，只有"网络那一跳"是假的。
"""
from __future__ import annotations

from typing import Any

from kingdee_ontology.base.dispatch import Dispatcher
from kingdee_ontology.base.ontology import Ontology, load
from kingdee_ontology.base.transport import FakeTransport

# 两个演示名词特意选得"业务归口"不同，给 A2A demo 用：
#   STK_Inventory（即时库存，仓库口径）与 SAL_SaleOrder（销售订单，销售口径）。
_SAMPLE_ROWS: dict[str, list[dict]] = {
    "STK_Inventory": [
        {"FMaterialId.FNumber": "M-1001", "FMaterialId.FName": "六角螺栓 M8",
         "FStockId.FName": "原材料仓", "FStockLocId.FName": "A-03-02",
         "FBaseQty": 1280, "FUnitId.FName": "个"},
        {"FMaterialId.FNumber": "M-2007", "FMaterialId.FName": "不锈钢板 2mm",
         "FStockId.FName": "原材料仓", "FStockLocId.FName": "B-01-01",
         "FBaseQty": 46, "FUnitId.FName": "张"},
    ],
    "SAL_SaleOrder": [
        {"FID": 10001, "FBillNo": "XSDD000101", "FDate": "2026-10-20",
         "FDocumentStatus": "C", "FCustId.FName": "示例客户 A",
         "FSalesOrgId.FName": "示例销售组织", "FTotalAmount": 48600.0,
         "FLinkQty": 120, "FStockOutQty": 80, "FDeliQty": 80},
    ],
}


# 第二套示例数据——演示"真·多账套"：跟 _SAMPLE_ROWS 不是同一份数据换了
# 权限视角，是完全独立的另一个账套（见 tenancy.DEMO_TENANT_B_ID）。
_ALT_SAMPLE_ROWS: dict[str, list[dict]] = {
    "STK_Inventory": [
        {"FMaterialId.FNumber": "M-9001", "FMaterialId.FName": "液压油缸",
         "FStockId.FName": "B 账套仓库", "FStockLocId.FName": "C-02-01",
         "FBaseQty": 320, "FUnitId.FName": "个"},
    ],
    "SAL_SaleOrder": [
        {"FID": 20002, "FBillNo": "XSDD000777", "FDate": "2026-10-28",
         "FDocumentStatus": "C", "FCustId.FName": "B 账套客户",
         "FSalesOrgId.FName": "B 账套销售组织", "FTotalAmount": 9900.0,
         "FLinkQty": 10, "FStockOutQty": 10, "FDeliQty": 10},
    ],
}


def _make_transport(sample_rows: dict[str, list[dict]]) -> FakeTransport:
    class _DemoTransport(FakeTransport):
        """按 form_id 分发预置示例行；查不到的名词给空列表，而不是报错。"""

        async def query(self, form_id: str, fields: str, filter_string: str, top: int) -> Any:
            self.calls.append(("query", form_id,
                               {"filter": filter_string, "top": top, "fields": fields}))
            return list(sample_rows.get(form_id, []))[:top]

    return _DemoTransport()


_tenant_dispatchers: dict[str, Dispatcher] = {}
_DEFAULT_KEY = "__default__"


def dispatcher_for_tenant(tenant_id: str, profile: str, alt_dataset: bool = False) -> Dispatcher:
    """每个租户一份独立的 Dispatcher + 示例数据——不是共享一份数据按角色
    过滤，是真的两份数据，用来证明"跨租户的 A2A 拿到的是目标租户自己的
    数据"而不是同一份数据换了个权限视角。"""
    if tenant_id not in _tenant_dispatchers:
        from kingdee_console.ontology_editor import ensure_profile
        if profile:
            ensure_profile(profile)
        rows = _ALT_SAMPLE_ROWS if alt_dataset else _SAMPLE_ROWS
        _tenant_dispatchers[tenant_id] = Dispatcher(
            ontology=load(tenant=profile), transport=_make_transport(rows),
            actor=f"console-demo:{tenant_id}")
    return _tenant_dispatchers[tenant_id]


def reset_tenant_dispatcher(tenant_id: str) -> None:
    _tenant_dispatchers.pop(tenant_id, None)


def reset_all_dispatchers() -> None:
    """测试用：清掉所有租户的缓存 Dispatcher，不止默认那一个。"""
    _tenant_dispatchers.clear()


def dispatcher() -> Dispatcher:
    """控制台自己（单租户视角：Dashboard/对话/直接调用）用的默认 Dispatcher——
    等价于 tenancy.DEMO_TENANT_ID 那个租户。"""
    from kingdee_console.ontology_editor import DEMO_PROFILE
    return dispatcher_for_tenant(_DEFAULT_KEY, DEMO_PROFILE)


def reset_dispatcher() -> None:
    """Ontology 编辑器改了 profile.yml 之后调这个——`load()` 的 lru_cache
    已经在 ontology_editor.add_link() 里清过了，但这里缓存的 Dispatcher
    实例还攥着旧的 Ontology 对象，不重建看不到新写的下推关系。"""
    reset_tenant_dispatcher(_DEFAULT_KEY)


def ontology() -> Ontology:
    return dispatcher().o


_installed = False


def install() -> None:
    """把 base/server.py 的 Dispatcher 工厂 `_d` 换成演示版。

    只换这一个名字；11 个 @mcp.tool 的注册、schema、文档字符串原样不动。
    幂等——重复调用没有副作用。
    """
    global _installed
    if _installed:
        return
    from kingdee_ontology.base import server as base_server
    base_server._d = dispatcher
    _installed = True
