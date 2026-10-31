"""FastAPI 端到端：Dashboard/对话/A2A 三组 API。

需要 `pip install -e ".[console]"`——核心逻辑（catalog/tenancy/a2a/intent）
不依赖 FastAPI，CI 默认只装 `[test]`，没装 `[console]` 时这个文件整体跳过，
其余 tests/console/ 照常跑（也正因为这样才知道 FastAPI 层以下不依赖它）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

pytest.importorskip("fastapi", reason="需要 pip install -e \".[console]\" 才能测 HTTP 层")

from fastapi.testclient import TestClient  # noqa: E402

from kingdee_console import tenancy  # noqa: E402
from kingdee_console.app import create_app  # noqa: E402


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


class FakeMessages:
    def __init__(self, script):
        self.script = list(script)

    def create(self, **kw):
        return self.script.pop(0) if len(self.script) > 1 else self.script[0]


class FakeClient:
    def __init__(self, script):
        self.messages = FakeMessages(script)


@pytest.fixture
def client(seeded, monkeypatch):
    # 聊天路由内部自己 new 一个 IntentEngine，不经过测试代码——
    # 打真实 Anthropic API 既不该在单测里发生，也没有网络/key。
    # 固定一段"查库存"脚本，覆盖 _client_or_create()。
    script = [
        Resp(content=[Block(type="tool_use", id="t1", name="kd_query",
                            input={"params": {"noun": "库存"}})]),
        Resp(content=[Block(type="text", text="库存查到了 2 条记录。")]),
    ]
    from kingdee_console.intent import IntentEngine
    monkeypatch.setattr(IntentEngine, "_client_or_create", lambda self: FakeClient(script))
    return TestClient(create_app())


def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_catalog_endpoint_has_colored_entries(client):
    body = client.get("/api/catalog").json()
    assert body["summary"]["total_nouns"] >= 80
    entry = next(e for e in body["entries"] if e["noun"] == "STK_Inventory")
    assert entry["color"]["label"] == "视图/查询"


def test_tools_endpoint_lists_eleven_kd_tools(client):
    body = client.get("/api/tools").json()
    assert len(body["tools"]) == 11
    assert body["demo_mode"] is True


def test_direct_call_bypasses_llm(client):
    r = client.post("/api/tools/kd_query/call", json={"args": {"params": {"noun": "库存"}}})
    assert r.status_code == 200
    assert r.json()["noun"] == "STK_Inventory"


def test_dashboard_tenant_role_assistant_crud(client):
    tenants_before = len(client.get("/api/tenants").json())
    t = client.post("/api/tenants", json={"name": "新租户"}).json()
    r = client.post("/api/roles", json={"name": "新角色", "allowed_nouns": ["SAL_SaleOrder"]}).json()
    a = client.post("/api/assistants",
                    json={"name": "新助理", "tenant_id": t["id"], "role_id": r["id"]}).json()
    assert len(client.get("/api/tenants").json()) == tenants_before + 1
    assert a["tenant_id"] == t["id"] and a["role_id"] == r["id"]


def test_create_assistant_rejects_unknown_tenant(client):
    r = client.post("/api/assistants",
                    json={"name": "x", "tenant_id": "不存在", "role_id": tenancy.ROLE_SALES_ID})
    assert r.status_code == 404


def test_conversation_lifecycle(client):
    conv = client.post("/api/conversations",
                       json={"assistant_id": tenancy.ASSISTANT_SALES_ID, "title": "测试对话"}).json()
    assert conv["title"] == "测试对话"

    listed = client.get("/api/conversations", params={"assistant_id": tenancy.ASSISTANT_SALES_ID}).json()
    assert any(c["id"] == conv["id"] for c in listed)

    renamed = client.patch(f"/api/conversations/{conv['id']}", json={"title": "改名了"}).json()
    assert renamed["title"] == "改名了"

    client.delete(f"/api/conversations/{conv['id']}")
    assert client.get(f"/api/conversations/{conv['id']}").status_code == 404


def test_send_message_runs_intent_engine_and_colors_the_reply(client):
    conv = client.post("/api/conversations",
                       json={"assistant_id": tenancy.ASSISTANT_SALES_ID}).json()
    reply = client.post(f"/api/conversations/{conv['id']}/messages",
                        json={"content": "查一下库存"}).json()

    assert reply["role"] == "assistant"
    assert reply["content"] == "库存查到了 2 条记录。"
    assert reply["capability_tags"][0]["noun"] == "STK_Inventory"
    assert reply["capability_tags"][0]["category"] == "view"

    history = client.get(f"/api/conversations/{conv['id']}/messages").json()
    assert [m["role"] for m in history] == ["user", "assistant"]


def test_send_message_degrades_gracefully_when_llm_unavailable(seeded, monkeypatch):
    """没配 ANTHROPIC_API_KEY（或任何意图识别失败）不该把整个请求炸成 500——
    错误原因应该作为一条助理消息留在对话历史里。"""
    from kingdee_console.app import create_app
    from kingdee_console.intent import IntentEngine

    def _boom(self):
        raise RuntimeError("没有配置 ANTHROPIC_API_KEY")

    monkeypatch.setattr(IntentEngine, "_client_or_create", _boom)
    c = TestClient(create_app())
    conv = c.post("/api/conversations", json={"assistant_id": tenancy.ASSISTANT_SALES_ID}).json()
    reply = c.post(f"/api/conversations/{conv['id']}/messages", json={"content": "你好"})

    assert reply.status_code == 200
    body = reply.json()
    assert "ANTHROPIC_API_KEY" in body["content"]
    assert body["role"] == "assistant"


def test_a2a_request_endpoint(client):
    body = client.post("/api/a2a/request", json={
        "from_assistant_id": tenancy.ASSISTANT_SALES_ID,
        "to_assistant_id": tenancy.ASSISTANT_WAREHOUSE_ID,
        "verb": "query", "noun": "库存",
    }).json()
    assert body["ok"] is True
    assert body["provenance"]["executed_by"] == "仓库助理"

    log = client.get("/api/a2a/log").json()
    assert len(log) == 1
