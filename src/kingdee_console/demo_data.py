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


class _DemoTransport(FakeTransport):
    """按 form_id 分发预置示例行；查不到的名词给空列表，而不是报错。"""

    async def query(self, form_id: str, fields: str, filter_string: str, top: int) -> Any:
        self.calls.append(("query", form_id,
                           {"filter": filter_string, "top": top, "fields": fields}))
        return list(_SAMPLE_ROWS.get(form_id, []))[:top]


_dispatcher: Dispatcher | None = None


def dispatcher() -> Dispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = Dispatcher(ontology=load(tenant=""), transport=_DemoTransport(),
                                 actor="console-demo")
    return _dispatcher


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
