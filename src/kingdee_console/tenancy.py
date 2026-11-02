"""多租户 / 角色 / 助理 的抽象骨架。

对应用户的原话："对于多租户也做一个抽象，方便后续做企业级的 A2A，
比如我的助理问其他角色继承权限的助理其他业务归口能力的数据"。

三层模型：

    Tenant（租户）   —— 一个金蝶账套。字段 `profile` 对应
                        profiles/<profile>/profile.yml（见
                        kingdee_ontology.base.ontology.profile_roots）；
                        `env_file` 指向这个租户的 KINGDEE_* 凭据文件路径
                        （部署机器的文件系统上，内容从不进 sqlite）——
                        tenant_pool.py 给这个租户的子进程注入
                        KINGDEE_ENV_FILE 用，真正做到"多账套同时在线"。
    Role（角色）     —— 业务归口的权限边界：这个角色能碰哪些名词
                        （allowed_nouns，form_id 集合）。动词层面的
                        允许/禁止仍然由本体自己的 allowed_verbs 兜底——
                        角色只收紧，不放宽。
    Assistant（助理） —— 绑定在某个 (tenant, role) 上的一个"身份"。
                        对话窗口的每个会话都挂在某个助理名下；A2A 请求
                        的 from/to 也都是助理 id。

RBAC 判断只有一条规则：`role.can(noun) == noun in role.allowed_nouns`。
没写进 allowed_nouns 的名词，这个角色的助理既不能直接查，也不能让
别的助理替它越权查——必须通过 A2A 向真正持有该名词权限的助理求助
（见 a2a.py），这正是"继承权限的助理"场景要演示的边界。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from kingdee_console.db import connect


@dataclass(frozen=True)
class Tenant:
    id: str
    name: str
    profile: str = ""
    env_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "profile": self.profile,
                "env_file": self.env_file}


@dataclass(frozen=True)
class Role:
    id: str
    name: str
    allowed_nouns: frozenset[str] = field(default_factory=frozenset)

    def can(self, noun_form_id: str) -> bool:
        return noun_form_id in self.allowed_nouns

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name,
                "allowed_nouns": sorted(self.allowed_nouns)}


@dataclass(frozen=True)
class Assistant:
    id: str
    name: str
    tenant_id: str
    role_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name,
                "tenant_id": self.tenant_id, "role_id": self.role_id}


def create_tenant(name: str, profile: str = "", env_file: str = "",
                  id: Optional[str] = None) -> Tenant:
    t = Tenant(id=id or str(uuid.uuid4()), name=name, profile=profile, env_file=env_file)
    with connect() as c:
        c.execute("INSERT INTO tenants (id, name, profile, env_file) VALUES (?, ?, ?, ?)",
                  (t.id, t.name, t.profile, t.env_file))
        c.commit()
    return t


def create_role(name: str, allowed_nouns: list[str], id: Optional[str] = None) -> Role:
    r = Role(id=id or str(uuid.uuid4()), name=name, allowed_nouns=frozenset(allowed_nouns))
    with connect() as c:
        c.execute("INSERT INTO roles (id, name, allowed_nouns) VALUES (?, ?, ?)",
                  (r.id, r.name, json.dumps(sorted(r.allowed_nouns), ensure_ascii=False)))
        c.commit()
    return r


def create_assistant(name: str, tenant_id: str, role_id: str,
                     id: Optional[str] = None) -> Assistant:
    a = Assistant(id=id or str(uuid.uuid4()), name=name, tenant_id=tenant_id, role_id=role_id)
    with connect() as c:
        c.execute("INSERT INTO assistants (id, name, tenant_id, role_id) VALUES (?, ?, ?, ?)",
                  (a.id, a.name, a.tenant_id, a.role_id))
        c.commit()
    return a


def list_tenants() -> list[Tenant]:
    with connect() as c:
        rows = c.execute("SELECT * FROM tenants ORDER BY created_at").fetchall()
    return [Tenant(id=r["id"], name=r["name"], profile=r["profile"], env_file=r["env_file"])
            for r in rows]


def list_roles() -> list[Role]:
    with connect() as c:
        rows = c.execute("SELECT * FROM roles ORDER BY created_at").fetchall()
    return [Role(id=r["id"], name=r["name"], allowed_nouns=frozenset(json.loads(r["allowed_nouns"])))
            for r in rows]


def list_assistants() -> list[Assistant]:
    with connect() as c:
        rows = c.execute("SELECT * FROM assistants ORDER BY created_at").fetchall()
    return [Assistant(id=r["id"], name=r["name"], tenant_id=r["tenant_id"], role_id=r["role_id"])
            for r in rows]


def get_role(role_id: str) -> Optional[Role]:
    with connect() as c:
        r = c.execute("SELECT * FROM roles WHERE id = ?", (role_id,)).fetchone()
    if r is None:
        return None
    return Role(id=r["id"], name=r["name"], allowed_nouns=frozenset(json.loads(r["allowed_nouns"])))


def get_assistant(assistant_id: str) -> Optional[Assistant]:
    with connect() as c:
        r = c.execute("SELECT * FROM assistants WHERE id = ?", (assistant_id,)).fetchone()
    if r is None:
        return None
    return Assistant(id=r["id"], name=r["name"], tenant_id=r["tenant_id"], role_id=r["role_id"])


def get_tenant(tenant_id: str) -> Optional[Tenant]:
    with connect() as c:
        r = c.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    if r is None:
        return None
    return Tenant(id=r["id"], name=r["name"], profile=r["profile"], env_file=r["env_file"])


# ── 演示种子数据 —— 固定 id，方便测试/前端直接引用 ────────────────
DEMO_TENANT_ID = "tenant-demo"
# 第二个租户：不是同租户换角色，是**换账套**——跟 DEMO_TENANT_ID 的数据
# 完全独立（见 demo_data.py 的 _ALT_SAMPLE_ROWS），证明 A2A 跨租户时
# 拿到的是目标租户自己的数据，不是同一份数据换了个权限视角。
DEMO_TENANT_B_ID = "tenant-demo-b"
ROLE_SALES_ID = "role-sales"
ROLE_WAREHOUSE_ID = "role-warehouse"
ASSISTANT_SALES_ID = "assistant-sales"
ASSISTANT_WAREHOUSE_ID = "assistant-warehouse"
ASSISTANT_WAREHOUSE_B_ID = "assistant-warehouse-b"


def ensure_seed_data() -> None:
    """幂等地种一套演示数据：两个租户（演示真·多账套隔离）+
    销售/仓库两个角色（角色跨租户复用，同一套权限定义） + 三个助理。

    销售助理（租户 A）只被授权碰 SAL_SaleOrder（销售订单，销售口径）；
    仓库助理（租户 A）只被授权碰 STK_Inventory（即时库存，仓库口径）——
    两边业务归口刻意不同，用来演示 a2a.py 里"问别的角色借数据"的场景。
    仓库助理 B（租户 B，另一个账套）跟仓库助理同角色、不同租户——
    演示"同角色不同账套"时数据真的不一样（见 test_tenant_pool.py）。
    """
    if get_tenant(DEMO_TENANT_ID) is not None:
        return
    create_tenant("演示租户 A", profile="", id=DEMO_TENANT_ID)
    create_tenant("演示租户 B（另一个账套）", profile="", id=DEMO_TENANT_B_ID)
    create_role("销售", ["SAL_SaleOrder"], id=ROLE_SALES_ID)
    create_role("仓库", ["STK_Inventory"], id=ROLE_WAREHOUSE_ID)
    create_assistant("销售助理", DEMO_TENANT_ID, ROLE_SALES_ID, id=ASSISTANT_SALES_ID)
    create_assistant("仓库助理", DEMO_TENANT_ID, ROLE_WAREHOUSE_ID, id=ASSISTANT_WAREHOUSE_ID)
    create_assistant("仓库助理（B 账套）", DEMO_TENANT_B_ID, ROLE_WAREHOUSE_ID,
                     id=ASSISTANT_WAREHOUSE_B_ID)
