"""意图识别 —— 把用户的自然语言变成一次（或几次）kd_* 工具调用。

用户原话："意图识别也做（做到隔离mcp信息的harness级别，推荐包一个 DSL
进来），但是保留本身直接访问的能力"——

Claude 看到的"工具"就是 base/server.py 里真实的 11 个 kd_* 工具
（list_tools() 拿到的 name/description/inputSchema），不是另造的一套
专用 DSL；这些工具本来就是"查询/写操作"的通用动词接口，Claude 选工具、
填 noun/verb 参数，执行永远经过 gateway.py 这一层——它只把工具名、
参数 schema、调用结果交给 LLM，金蝶的 session/账套凭据从没出现在
发给 Claude 的任何一条消息里，这就是"隔离 mcp 信息的 harness 级别"。

"保留本身直接访问的能力"由 routers/dashboard.py 的直接调用端点满足——
同一个 gateway，跳过这里的 LLM 循环，直接 call_tool。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from kingdee_console.catalog import tags_from_dispatch_result
from kingdee_console.gateway import McpGateway, ToolSchema

SYSTEM_PROMPT = (
    "你是金蝶云星空 ERP 的助理。可用工具是本体底座的通用动词工具——"
    "查询用 kd_query，写操作统一用 kd_act（verb 字段指定 submit/audit/...），"
    "不确定有哪些单据/动词/状态时先用 kd_describe 自己查，不要猜 form_id，"
    "可以直接把用户说的中文名/别名传给 noun 参数，底层会自动解析。"
    "回答时用简洁的中文说明查到/做了什么，不要重复贴大段原始 JSON。"
)

MAX_TOOL_ROUNDS = 4


@dataclass
class ToolInvocation:
    tool: str
    args: dict
    result: dict
    capability_tags: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"tool": self.tool, "args": self.args, "result": self.result,
                "capability_tags": self.capability_tags}


@dataclass
class IntentResult:
    text: str
    invocations: list[ToolInvocation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "tool_calls": [i.to_dict() for i in self.invocations]}


def _tool_schema(t: ToolSchema) -> dict:
    return {"name": t.name, "description": t.description, "input_schema": t.input_schema}


class IntentEngine:
    """client 可注入——测试时传一个只实现 `.messages.create(**kw)` 的假对象，
    不必打真的 Anthropic API。不传时惰性创建一个真的 anthropic.Anthropic()。
    """

    def __init__(self, gateway: Optional[McpGateway] = None, client: Any = None,
                 model: str = "claude-sonnet-5"):
        self.gateway = gateway or McpGateway()
        self._client = client
        self.model = model

    def _client_or_create(self) -> Any:
        if self._client is not None:
            return self._client
        import anthropic
        self._client = anthropic.Anthropic()
        return self._client

    async def resolve(self, user_text: str, history: Optional[list[dict]] = None) -> IntentResult:
        tools = [_tool_schema(t) for t in await self.gateway.list_tools()]
        messages: list[dict] = list(history or []) + [{"role": "user", "content": user_text}]
        client = self._client_or_create()
        invocations: list[ToolInvocation] = []

        for _ in range(MAX_TOOL_ROUNDS):
            response = client.messages.create(
                model=self.model, max_tokens=1024, system=SYSTEM_PROMPT,
                tools=tools, messages=messages,
            )
            tool_uses = [b for b in response.content if getattr(b, "type", "") == "tool_use"]
            if not tool_uses:
                text = "".join(b.text for b in response.content
                               if getattr(b, "type", "") == "text")
                return IntentResult(text=text, invocations=invocations)

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for use in tool_uses:
                args = dict(use.input or {})
                result = await self.gateway.call_tool(use.name, args)
                tags = tags_from_dispatch_result(self.gateway.ontology, use.name, result)
                invocations.append(ToolInvocation(
                    tool=use.name, args=args, result=result,
                    capability_tags=[t.to_dict() for t in tags],
                ))
                tool_results.append({
                    "type": "tool_result", "tool_use_id": use.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })
            messages.append({"role": "user", "content": tool_results})

        return IntentResult(
            text="工具调用轮数超过上限，已提前结束——请换个更具体的问法。",
            invocations=invocations)
