"""MCP 网关 —— 整个控制台里唯一一处"调用现有 MCP 接口"的地方。

真实模式：在同一进程里直接拿 kingdee_ontology.base.server 的 FastMCP
实例调 list_tools()/call_tool()——这就是字面意义上的"用 python 调用
现有的 mcp 接口"，走的是和真实 MCP client/stdio 完全相同的工具注册表、
校验、分发代码，只是省了一层 stdio 序列化（同进程没必要多绕一圈）。
登录态复用 kingdee_mcp.server 模块级的 _session_id 缓存——网关本身
不管连接池/子进程生命周期，"避免反复登录"这件事已经由那层缓存解决；
进程不运行时自然"用完即走"，没有额外要手动关闭的常驻连接。

演示模式（默认；没配 KINGDEE_USERNAME 时自动生效，或显式设
KINGDEE_CONSOLE_DEMO=1/0）：把 base/server.py 的 Dispatcher 工厂换成
demo_data.py 里注入 FakeTransport 的版本，11 个 kd_* 工具的名字/
描述/schema 原样不变，只是最后一跳不连真账套。Dashboard/对话/A2A
demo 因此可以在没有真实金蝶凭据的环境里完整跑通。

无论哪种模式，调用方（对话界面、Dashboard、其它 agent 的 A2A 请求）
都只拿到本模块返回的"工具名 + 结构化结果"——拿不到金蝶的 session/
账套凭据，那些字段从没越过这一层。这正是用户要的"python 隔一层，
避免其他 agent 直接拿到 mcp 里面的密钥和账套信息"。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ToolSchema:
    name: str
    description: str
    input_schema: dict


def _demo_enabled(explicit: Optional[bool]) -> bool:
    if explicit is not None:
        return explicit
    env = os.environ.get("KINGDEE_CONSOLE_DEMO")
    if env is not None:
        return env == "1"
    # 没配真账套环境变量时，自动落到演示模式——免得第一次启动就报连接错误
    return not os.environ.get("KINGDEE_USERNAME")


def _unwrap(content: Any) -> dict[str, Any]:
    """FastMCP.call_tool(convert_result=True) 实测回的是
    (list[ContentBlock], structuredContent) 这个二元组——kd_* 工具的返回
    值是个 str（_fmt() 序列化好的 JSON），所以 structuredContent 形如
    {"result": "<json 字符串>"}。这里把它解开成真正的结构化结果；
    没有 structuredContent 或解不出来时退回去读 ContentBlock 的 text。
    """
    if isinstance(content, tuple) and len(content) == 2:
        blocks, structured = content
        if isinstance(structured, dict):
            raw = structured.get("result")
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except Exception:
                    return {"raw": raw}
            return structured
        content = blocks
    if isinstance(content, dict):
        return content
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            try:
                return json.loads(text)
            except Exception:
                return {"raw": text}
    return {"raw": str(content)}


class McpGateway:
    """包一层 kingdee_ontology.base 的 FastMCP 服务端（11 个 kd_* 工具）。"""

    def __init__(self, demo: Optional[bool] = None):
        self.demo = _demo_enabled(demo)
        if self.demo:
            from kingdee_console import demo_data
            demo_data.install()

    async def list_tools(self) -> list[ToolSchema]:
        from kingdee_ontology.base.server import mcp as base_mcp
        tools = await base_mcp.list_tools()
        return [ToolSchema(name=t.name, description=t.description or "",
                            input_schema=t.inputSchema or {}) for t in tools]

    async def call_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        from kingdee_ontology.base.server import mcp as base_mcp
        content = await base_mcp.call_tool(name, arguments)
        return _unwrap(content)

    @property
    def ontology(self):
        """供 catalog.py 反推能力标签、tenancy.py 做 RBAC 查询用的本体实例。"""
        if self.demo:
            from kingdee_console import demo_data
            return demo_data.ontology()
        from kingdee_ontology.base.ontology import load
        return load(tenant=os.environ.get("KINGDEE_TENANT", ""))


_default_gateway: Optional[McpGateway] = None


def default_gateway() -> McpGateway:
    """单进程内共享的默认网关——避免每个请求都重新判断一次 demo 模式。"""
    global _default_gateway
    if _default_gateway is None:
        _default_gateway = McpGateway()
    return _default_gateway
