"""工具调用事件总线：三条调用路径（直接调用/对话/A2A）都要广播事件。"""
from __future__ import annotations

import asyncio

from kingdee_console import a2a, tenancy
from kingdee_console.events import bus
from kingdee_console.gateway import McpGateway


def test_direct_call_publishes_event(seeded):
    gw = McpGateway()
    before = len(bus.history)
    asyncio.run(gw.call_tool("kd_query", {"params": {"noun": "库存"}}))
    assert len(bus.history) == before + 1
    ev = bus.history[-1]
    assert ev.source == "direct"
    assert ev.ok is True
    assert ev.capability_tags[0]["noun"] == "STK_Inventory"


def test_a2a_call_publishes_event_tagged_a2a(seeded):
    before = len(bus.history)
    asyncio.run(a2a.request(tenancy.ASSISTANT_SALES_ID, tenancy.ASSISTANT_WAREHOUSE_ID,
                            "query", "库存"))
    assert len(bus.history) == before + 1
    assert bus.history[-1].source == "a2a"


def test_subscribers_receive_events_via_queue(seeded):
    gw = McpGateway()
    q = bus.subscribe()
    try:
        asyncio.run(gw.call_tool("kd_query", {"params": {"noun": "库存"}}))
        event = q.get_nowait()
        assert event.tool == "kd_query"
    finally:
        bus.unsubscribe(q)


def test_history_is_capped(seeded, monkeypatch):
    from kingdee_console import events as events_mod
    monkeypatch.setattr(events_mod, "bus", events_mod.EventBus(history_size=3))
    small_bus = events_mod.bus
    # gateway.py 内部用 `from kingdee_console.events import bus`，运行时解析，
    # 所以 monkeypatch 模块属性之后新调用会用到新 bus。
    import kingdee_console.gateway as gw_mod
    gw = gw_mod.McpGateway()
    for _ in range(5):
        asyncio.run(gw.call_tool("kd_query", {"params": {"noun": "库存"}}))
    assert len(small_bus.history) == 3
