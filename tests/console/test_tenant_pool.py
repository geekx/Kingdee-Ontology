"""真实模式（子进程）网关：env 构造正确、池按租户缓存、空闲自动断开。

没有真实金蝶凭据可测，所以这里不起真子进程——跟 base/server.py 的
_guard 签名问题当初的排查手法一样：把 mcp.client.stdio.stdio_client /
mcp.ClientSession 换成假的，验证"这段代码真的会这样调用它们"，而不是
验证金蝶那头真的通了（那部分留给有真账套的人在真实部署里验证）。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from kingdee_console.tenancy import Tenant
from kingdee_console.tenant_pool import SubprocessTenantGateway, TenantGatewayPool


@dataclass
class _FakeToolsResult:
    tools: list = field(default_factory=list)


class _FakeStdioCM:
    def __init__(self, params, log: list):
        self.params = params
        self.log = log

    async def __aenter__(self):
        self.log.append(dict(self.params.env))
        return ("read-stream", "write-stream")

    async def __aexit__(self, *exc):
        return False


class _FakeClientSession:
    instances: list = []

    def __init__(self, read, write):
        self.closed = False
        _FakeClientSession.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.closed = True
        return False

    async def initialize(self):
        pass

    async def list_tools(self):
        return _FakeToolsResult(tools=[])

    async def call_tool(self, name, arguments):
        return ({"ok": True, "noun": "STK_Inventory", "zh": "即时库存", "count": 0, "rows": []}, None)


@pytest.fixture
def fake_stdio(monkeypatch):
    connect_log: list = []
    _FakeClientSession.instances = []

    def fake_stdio_client(params):
        return _FakeStdioCM(params, connect_log)

    monkeypatch.setattr("mcp.client.stdio.stdio_client", fake_stdio_client)
    monkeypatch.setattr("mcp.ClientSession", _FakeClientSession)
    return connect_log


def test_subprocess_gateway_injects_tenant_env_file_and_profile(fake_stdio, seeded):
    tenant = Tenant(id="t1", name="客户 A", profile="tenant-a", env_file="/secure/tenant-a.env")
    gw = SubprocessTenantGateway(tenant)

    asyncio.run(gw.list_tools())

    assert len(fake_stdio) == 1
    env = fake_stdio[0]
    assert env["KINGDEE_ENV_FILE"] == "/secure/tenant-a.env"
    assert env["KINGDEE_TENANT"] == "tenant-a"
    asyncio.run(gw.close())


def test_subprocess_gateway_reuses_connection_across_calls(fake_stdio, seeded):
    """"避免反复登录"：同一个网关对象连续调用只连一次子进程。"""
    tenant = Tenant(id="t1", name="客户 A", profile="", env_file="")
    gw = SubprocessTenantGateway(tenant)

    asyncio.run(gw.list_tools())
    asyncio.run(gw.call_tool("kd_query", {"params": {"noun": "库存"}}))
    asyncio.run(gw.call_tool("kd_query", {"params": {"noun": "库存"}}))

    assert len(fake_stdio) == 1               # 三次调用，只建了一次连接
    asyncio.run(gw.close())


def test_subprocess_gateway_closes_idle_connection_and_reconnects(fake_stdio, seeded):
    tenant = Tenant(id="t1", name="客户 A", profile="", env_file="")
    gw = SubprocessTenantGateway(tenant, idle_timeout=0.05)

    async def run():
        await gw.list_tools()
        assert len(fake_stdio) == 1
        await asyncio.sleep(0.3)              # 超过 idle_timeout，等空闲回收跑一轮
        assert _FakeClientSession.instances[0].closed is True
        await gw.list_tools()                 # 再调一次，应该重新连
        assert len(fake_stdio) == 2
        await gw.close()

    asyncio.run(run())


def test_pool_caches_one_gateway_per_tenant(seeded):
    from kingdee_console.tenant_pool import TenantDemoGateway

    pool = TenantGatewayPool()
    tenant_a = Tenant(id="ta", name="A", profile="")
    tenant_b = Tenant(id="tb", name="B", profile="")

    g1 = pool.get(tenant_a, demo=True)
    g2 = pool.get(tenant_a, demo=True)
    g3 = pool.get(tenant_b, demo=True)

    assert isinstance(g1, TenantDemoGateway)
    assert g1 is g2                           # 同一个租户复用同一个网关对象
    assert g1 is not g3                       # 不同租户互不相同


def test_pool_demo_and_real_caches_are_independent(fake_stdio, seeded):
    pool = TenantGatewayPool()
    tenant = Tenant(id="t1", name="A", profile="")

    demo_gw = pool.get(tenant, demo=True)
    real_gw = pool.get(tenant, demo=False)

    assert demo_gw is not real_gw
    assert isinstance(real_gw, SubprocessTenantGateway)
