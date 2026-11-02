"""工具调用事件总线 —— Ontology 节点流向监测动效的数据源。

gateway.call_tool() 每次真正执行，都往这里广播一条事件：调用了哪个工具、
反推出的能力标签（跟 catalog.tags_from_dispatch_result 是同一套规则，
所以颜色/类别跟 Dashboard、对话窗口的 chip 完全一致）、来源
（chat/direct/a2a）。前端订阅 WebSocket，把事件映射成 Ontology 图上
节点/边的高亮动效——不是另起一条状态线，是同一次调用的实时镜像。
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallEvent:
    tool: str
    source: str                          # chat | direct | a2a
    capability_tags: list[dict]
    ok: bool
    at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "source": self.source,
                "capability_tags": self.capability_tags, "ok": self.ok, "at": self.at}


def publish_tool_call(ontology: Any, tool: str, result: dict, source: str) -> None:
    """三条网关实现（McpGateway / TenantDemoGateway / SubprocessTenantGateway）
    都调这一个函数广播事件——能力标签的反推规则只写一遍。"""
    from kingdee_console.catalog import tags_from_dispatch_result

    ok = not (isinstance(result, dict) and result.get("ok") is False)
    tags = tags_from_dispatch_result(ontology, tool, result)
    bus.publish(ToolCallEvent(tool=tool, source=source, ok=ok,
                              capability_tags=[t.to_dict() for t in tags]))


class EventBus:
    """进程内发布/订阅——控制台是单进程部署，不需要 Redis 之类的外部总线。"""

    def __init__(self, history_size: int = 50):
        self._subscribers: set[asyncio.Queue] = set()
        self._history: list[ToolCallEvent] = []
        self._history_size = history_size

    def publish(self, event: ToolCallEvent) -> None:
        self._history.append(event)
        if len(self._history) > self._history_size:
            self._history.pop(0)
        for q in list(self._subscribers):
            q.put_nowait(event)

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    @property
    def history(self) -> list[ToolCallEvent]:
        return list(self._history)


bus = EventBus()
