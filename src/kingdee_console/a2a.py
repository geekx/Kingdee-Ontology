"""A2A（助理对助理） —— 跨业务归口借数据的最小可跑通 demo。

场景（用户原话）："我的助理问其他角色继承权限的助理其他业务归口能力
的数据"：销售助理自己没有仓库权限，查不了即时库存；但可以发一个
A2A 请求给仓库助理，仓库助理用**自己的**权限把查到的数据带回来。

安全边界：
  1. 权限检查只认 to_assistant 自己的角色——from_assistant 不能借
     to_assistant 的身份去碰 to_assistant 都没被授权的东西，更不能
     靠这条路径绕开自己角色本来就没有的权限。
  2. from_assistant 拿到的永远是结构化结果 + 来源说明（谁执行的、
     用的哪个角色），不会拿到 to_assistant/租户的任何凭据——
     跟 gateway.py 对浏览器/对话界面的隔离是同一条边界。
  3. 每一次请求（不管允许还是拒绝）都落一条审计记录——拒绝的请求
     本身就是信号，不能因为"没做成"就不记。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional

from kingdee_console import tenancy
from kingdee_console.catalog import tags_from_dispatch_result
from kingdee_console.db import connect
from kingdee_console.gateway import McpGateway


@dataclass
class A2AResult:
    ok: bool
    trace_id: str
    reason: str = ""
    result: Optional[dict] = None
    provenance: Optional[dict] = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok, "trace_id": self.trace_id, "reason": self.reason}
        if self.result is not None:
            out["result"] = self.result
        if self.provenance is not None:
            out["provenance"] = self.provenance
        return out


def _log(trace_id: str, from_id: str, to_id: str, verb: str, noun: str,
         allowed: bool, reason: str) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO a2a_audit (id, trace_id, from_assistant_id, to_assistant_id, "
            "verb, noun, allowed, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), trace_id, from_id, to_id, verb, noun, int(allowed), reason))
        c.commit()


async def request(from_assistant_id: str, to_assistant_id: str, verb: str, noun: str,
                  args: Optional[dict] = None, gateway: Optional[McpGateway] = None) -> A2AResult:
    """from_assistant 向 to_assistant 发起一次跨业务归口的能力请求。

    权限只按 noun 的 form_id 判断，所以这里先用 to_assistant 自己那套
    本体把 noun（可能是中文名/别名）解析成 form_id，再查角色允许表——
    不能让"用别名绕过角色白名单"成为一个漏洞。
    """
    trace_id = str(uuid.uuid4())
    from_a = tenancy.get_assistant(from_assistant_id)
    to_a = tenancy.get_assistant(to_assistant_id)
    if from_a is None or to_a is None:
        _log(trace_id, from_assistant_id, to_assistant_id, verb, noun, False, "助理不存在")
        return A2AResult(ok=False, trace_id=trace_id, reason="助理不存在")

    gw = gateway or McpGateway()
    try:
        resolved = gw.ontology.resolve_noun(noun)
    except Exception as e:
        _log(trace_id, from_assistant_id, to_assistant_id, verb, noun, False, str(e))
        return A2AResult(ok=False, trace_id=trace_id, reason=str(e))

    to_role = tenancy.get_role(to_a.role_id)
    if to_role is None or not to_role.can(resolved.form_id):
        deny_reason = (f"{to_a.name}（角色：{to_role.name if to_role else '未知'}）"
                       f"没有被授权访问 {resolved.form_id}（{resolved.zh}）")
        _log(trace_id, from_assistant_id, to_assistant_id, verb, resolved.form_id, False, deny_reason)
        return A2AResult(ok=False, trace_id=trace_id, reason=deny_reason)

    # 11 个 kd_* 工具清一色是单个 `params: XInput` 参数——真实的 MCP
    # inputSchema 是 {"params": {...}}，不是把字段摊平在顶层（之前排查
    # base/server.py 的 _guard 签名丢失问题时顺带确认的，见 gateway.py）。
    call_args = dict(args or {})
    if verb == "query":
        params = {"noun": resolved.form_id, "filter": call_args.get("filter", ""),
                 "fields": call_args.get("fields", ""), "top": call_args.get("top", 50)}
        result = await gw.call_tool("kd_query", {"params": params})
        tool_name = "kd_query"
    else:
        params = {"verb": verb, "noun": resolved.form_id, **call_args}
        result = await gw.call_tool("kd_act", {"params": params})
        tool_name = "kd_act"

    _log(trace_id, from_assistant_id, to_assistant_id, verb, resolved.form_id, True, "")
    tags = tags_from_dispatch_result(gw.ontology, tool_name, result)
    return A2AResult(
        ok=True, trace_id=trace_id, result=result,
        provenance={
            "executed_by": to_a.name, "executed_by_role": to_role.name,
            "requested_by": from_a.name,
            "capabilities": [t.to_dict() for t in tags],
        },
    )


def audit_log(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM a2a_audit ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
