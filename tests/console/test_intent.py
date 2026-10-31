"""意图识别：Claude 选 kd_* 工具 + 填参数 → 真实 Dispatcher 执行 →
结果反推能力标签。全程用假的 Anthropic 客户端，不打真实 API。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from kingdee_console.gateway import McpGateway
from kingdee_console.intent import MAX_TOOL_ROUNDS, IntentEngine


@dataclass
class Block:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class Resp:
    content: list


class ScriptedMessages:
    """按顺序弹出预设响应；script 用完后固定返回最后一条。"""

    def __init__(self, script: list[Resp]):
        self.script = list(script)
        self.calls: list[dict] = []

    def create(self, **kw):
        self.calls.append(kw)
        return self.script.pop(0) if len(self.script) > 1 else self.script[0]


class FakeClient:
    def __init__(self, script: list[Resp]):
        self.messages = ScriptedMessages(script)


def test_resolve_picks_tool_then_summarizes(seeded):
    client = FakeClient([
        Resp(content=[Block(type="tool_use", id="t1", name="kd_query",
                            input={"params": {"noun": "库存"}})]),
        Resp(content=[Block(type="text", text="库存查到了 2 条记录。")]),
    ])
    engine = IntentEngine(gateway=McpGateway(), client=client)
    out = asyncio.run(engine.resolve("查一下库存"))

    assert out.text == "库存查到了 2 条记录。"
    assert len(out.invocations) == 1
    inv = out.invocations[0]
    assert inv.tool == "kd_query"
    assert inv.capability_tags[0]["noun"] == "STK_Inventory"
    assert inv.capability_tags[0]["category"] == "view"


def test_resolve_with_no_tool_use_returns_text_directly(seeded):
    client = FakeClient([Resp(content=[Block(type="text", text="你好，我能帮你查金蝶的数据。")])])
    engine = IntentEngine(gateway=McpGateway(), client=client)
    out = asyncio.run(engine.resolve("你好"))
    assert out.text == "你好，我能帮你查金蝶的数据。"
    assert out.invocations == []


def test_resolve_stops_after_max_rounds_instead_of_looping_forever(seeded):
    # 每一轮都再发一次 tool_use，永远不给最终文本——必须被轮数上限截住。
    endless_tool_use = Resp(content=[Block(type="tool_use", id="t1", name="kd_query",
                                           input={"params": {"noun": "库存"}})])
    client = FakeClient([endless_tool_use] * (MAX_TOOL_ROUNDS + 2))
    engine = IntentEngine(gateway=McpGateway(), client=client)
    out = asyncio.run(engine.resolve("查一下库存"))

    assert "轮数超过上限" in out.text
    assert len(out.invocations) == MAX_TOOL_ROUNDS
    assert len(client.messages.calls) == MAX_TOOL_ROUNDS


def test_tools_passed_to_claude_match_live_mcp_schema(seeded):
    """意图识别给 Claude 的工具列表必须是 base/server.py 真实的 11 个
    kd_* 工具及其 schema——不是另造的一套 DSL（见 intent.py 的设计说明）。"""
    client = FakeClient([Resp(content=[Block(type="text", text="ok")])])
    engine = IntentEngine(gateway=McpGateway(), client=client)
    asyncio.run(engine.resolve("随便问问"))

    tool_names = {t["name"] for t in client.messages.calls[0]["tools"]}
    assert tool_names == {"kd_describe", "kd_query", "kd_act", "kd_push", "kd_object",
                          "kd_read", "kd_report", "kd_run", "kd_saga", "kd_audit",
                          "kd_check_profile"}
