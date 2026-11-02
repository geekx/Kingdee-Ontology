"""按租户隔离的 MCP 网关池 —— 真·多账套 A2A 的落地点。

之前 a2a.py 固定用同一个共享网关执行所有请求：跨角色能演示权限边界，
但跨租户（真正意义上的"换账套"）不行——不管请求发给哪个助理，底层连的
都是同一个账套。这里补上"按租户换连接"这一层：

  演示模式：每个租户各自一套 FakeTransport 示例数据（kingdee_console 自己
  造的两套"虚拟账套"，见 demo_data.py 的 _SAMPLE_ROWS / _ALT_SAMPLE_ROWS），
  证明按租户隔离这件事本身是对的——不需要真账套也能看出"问另一个账套的
  助理，拿到的是那个账套自己的数据"，而不是同一份数据换了个权限视角。

  真实模式：每个租户一个独立子进程，跑的是同一份、完全没改过的
  kingdee_ontology.base.server（真的通过 MCP stdio 协议连接——这是
  gateway.py 设计时提到、但为了简化先没做的路径，多账套场景下才真正
  用得上：base/server.py 的 Dispatcher 工厂 `_d()` 和 kingdee_mcp.server
  的 `_session_id` 都是模块级全局，一个进程只能代表一个账套，要同时服务
  多个账套只能是多个进程）。子进程的账套凭据从 Tenant.env_file 指向的
  .env 文件来——那个文件只存在于部署这台机器的文件系统上，从来不进
  sqlite，也从不经过控制台的 HTTP API 往上层走（延续 gateway.py 的隔离
  边界）。空闲超过 idle_timeout 秒自动关闭子进程（"用完即走"），下次用
  到再按需拉起——这正是最早设计 gateway.py 时想做、后来因为同进程 FastMCP
  调用更简单而没做的那部分。
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from contextlib import AsyncExitStack
from typing import Any, Optional, Protocol

from kingdee_console.events import publish_tool_call
from kingdee_console.gateway import ToolSchema, unwrap_mcp_result
from kingdee_console.tenancy import Tenant


class TenantGateway(Protocol):
    """a2a.py 只依赖这三样——demo/真实两种实现、池不池化都不影响调用方。"""

    @property
    def ontology(self) -> Any: ...

    async def list_tools(self) -> list[ToolSchema]: ...

    async def call_tool(self, name: str, arguments: dict, source: str = "direct") -> dict[str, Any]: ...


class TenantDemoGateway:
    """演示模式下某个具体租户的网关。

    不走 FastMCP 的全局 `_d()` 工厂——那个工厂一次只能指向一个 Dispatcher，
    多租户并发用不了（见 demo_data.install() 的说明）。直接调 Dispatcher
    的方法，按工具名分发；目前只接 A2A demo 真正用得到的三个
    （kd_query/kd_act/kd_push），够用，不是要重新实现全部 11 个工具。
    """

    def __init__(self, tenant: Tenant):
        self.tenant = tenant
        self.demo = True

    @property
    def dispatcher(self):
        from kingdee_console import demo_data
        from kingdee_console.tenancy import DEMO_TENANT_B_ID
        return demo_data.dispatcher_for_tenant(
            self.tenant.id, self.tenant.profile, alt_dataset=self.tenant.id == DEMO_TENANT_B_ID)

    @property
    def ontology(self):
        return self.dispatcher.o

    async def list_tools(self) -> list[ToolSchema]:
        # schema 本身跟用哪个 Dispatcher 无关——FastMCP 的工具注册表是
        # 进程级的，读 schema 不需要经过某个具体租户的 Dispatcher。
        from kingdee_ontology.base.server import mcp as base_mcp
        tools = await base_mcp.list_tools()
        return [ToolSchema(name=t.name, description=t.description or "",
                           input_schema=t.inputSchema or {}) for t in tools]

    async def call_tool(self, name: str, arguments: dict, source: str = "direct") -> dict[str, Any]:
        params = arguments.get("params", {})
        d = self.dispatcher
        if name == "kd_query":
            result = await d.query(params["noun"], params.get("filter", ""),
                                   params.get("fields", ""), params.get("top", 50))
        elif name == "kd_act":
            result = await d.act(params["verb"], params["noun"], params.get("targets", []),
                                 model=params.get("model"), current_state=params.get("current_state"),
                                 operation=params.get("operation"), dry_run=params.get("dry_run", False))
        elif name == "kd_push":
            result = await d.push(params["source"], params["target"], params["source_bill_nos"],
                                  rule_id=params.get("rule_id", ""))
        else:
            raise ValueError(
                f"演示模式下 TenantDemoGateway 暂不支持 {name}（只接 kd_query/kd_act/kd_push）")

        publish_tool_call(self.ontology, name, result, source)
        return result


class SubprocessTenantGateway:
    """真实模式下某个具体租户的网关——自己的子进程，自己的账套凭据。"""

    def __init__(self, tenant: Tenant, idle_timeout: float = 600.0):
        self.tenant = tenant
        self.demo = False
        self.idle_timeout = idle_timeout
        self._session = None
        self._stack: Optional[AsyncExitStack] = None
        self._last_used = 0.0
        self._lock = asyncio.Lock()
        self._reaper: Optional[asyncio.Task] = None

    def _subprocess_env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self.tenant.env_file:
            env["KINGDEE_ENV_FILE"] = self.tenant.env_file
        if self.tenant.profile:
            env["KINGDEE_TENANT"] = self.tenant.profile
        return env

    async def _connect(self):
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        params = StdioServerParameters(
            command=sys.executable,
            args=["-c", "from kingdee_ontology.base.server import main; main()"],
            env=self._subprocess_env(),
        )
        self._stack = AsyncExitStack()
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return session

    async def _ensure(self):
        async with self._lock:
            self._last_used = time.monotonic()
            if self._session is None:
                self._session = await self._connect()
                if self._reaper is None:
                    self._reaper = asyncio.create_task(self._reap())
            return self._session

    async def _reap(self) -> None:
        try:
            while True:
                await asyncio.sleep(min(60.0, self.idle_timeout))
                if self._session is not None and time.monotonic() - self._last_used > self.idle_timeout:
                    await self._close_locked()
        except asyncio.CancelledError:
            pass

    async def _close_locked(self) -> None:
        async with self._lock:
            if self._stack is not None:
                await self._stack.aclose()
            self._session = None
            self._stack = None

    async def close(self) -> None:
        if self._reaper is not None:
            self._reaper.cancel()
            self._reaper = None
        await self._close_locked()

    @property
    def ontology(self):
        # 子进程是独立解释器，拿不到它内存里的 Ontology 对象；颜色标签只
        # 需要底座的公共部分（verb/noun/category），租户覆盖层的自定义
        # 名词在这里反推不出标签——能力标签退化但不报错，可接受的折中。
        from kingdee_ontology.base.ontology import load
        return load(tenant="")

    async def list_tools(self) -> list[ToolSchema]:
        session = await self._ensure()
        result = await session.list_tools()
        return [ToolSchema(name=t.name, description=t.description or "",
                           input_schema=t.inputSchema or {}) for t in result.tools]

    async def call_tool(self, name: str, arguments: dict, source: str = "direct") -> dict[str, Any]:
        session = await self._ensure()
        content = await session.call_tool(name, arguments)
        result = unwrap_mcp_result(content)
        publish_tool_call(self.ontology, name, result, source)
        return result


class TenantGatewayPool:
    """按 tenant_id 缓存网关——demo/真实各自一套缓存，互不影响。"""

    def __init__(self):
        self._demo: dict[str, TenantDemoGateway] = {}
        self._real: dict[str, SubprocessTenantGateway] = {}

    def get(self, tenant: Tenant, demo: bool) -> TenantGateway:
        if demo:
            if tenant.id not in self._demo:
                self._demo[tenant.id] = TenantDemoGateway(tenant)
            return self._demo[tenant.id]
        if tenant.id not in self._real:
            self._real[tenant.id] = SubprocessTenantGateway(tenant)
        return self._real[tenant.id]

    async def close_all(self) -> None:
        for gw in self._real.values():
            await gw.close()
        self._real.clear()
        self._demo.clear()


pool = TenantGatewayPool()
