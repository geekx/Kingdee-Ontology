"""Ontology 节点编辑器的持久化 —— 往"活跃 profile"的 links 段追加自定义下推关系。

不碰底座 registry.yml（共享基础设施，谁都不该从 Web UI 改它，改错一条
影响的是所有租户），只写 profiles/<profile>/profile.yml 的覆盖层——
跟 Ontology._merge() 的既有设计完全对齐：profile 只能新增/改写底座条目，
不能删除（见 base/ontology.py 的 Ontology.__init__ 说明）。目前只开放
"新增下推关系"这一种编辑——新增名词要填的字段（zh/category/allowed_verbs/
default_fields…）比一条 link 多得多，且牵涉颜色分类等约定，留给后续迭代。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

from kingdee_ontology.base.ontology import load

DEMO_PROFILE = "console-demo"


def runtime_profiles_dir() -> Path:
    """演示模式/编辑器用的可写 profile 目录——不碰仓库自带的 profiles/，
    避免把运行时产物写进源码树。KINGDEE_PROFILES 在
    kingdee_ontology.base.ontology.profile_roots() 里排第一优先级，
    设了之后 load(tenant=...) 会先找这里，不影响仓库自带的
    profiles/example-tenant 等真实示例。
    """
    from kingdee_console.db import db_path
    base = db_path().parent / ".kingdee_console_profiles"
    base.mkdir(parents=True, exist_ok=True)
    existing = os.environ.get("KINGDEE_PROFILES", "")
    paths = [p for p in existing.split(os.pathsep) if p]
    if str(base) not in paths:
        os.environ["KINGDEE_PROFILES"] = os.pathsep.join([str(base), *paths])
    return base


def ensure_profile(name: str) -> Path:
    """保证 profiles/<name>/profile.yml 存在，不存在就建一个最小骨架。"""
    root = runtime_profiles_dir()
    path = root / name / "profile.yml"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump({"tenant": name, "links": []}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    return path


def active_profile_name(demo: bool) -> str:
    """跟 gateway.py 的 ontology 属性用的是同一条判断逻辑——编辑器写的
    profile 必须跟正在跑的 Dispatcher 读的是同一个，否则改了却"看不见"。
    """
    return DEMO_PROFILE if demo else os.environ.get("KINGDEE_TENANT", "")


def add_link(profile: str, source: str, target: str, zh: str) -> dict[str, Any]:
    """往 profile 的 links 段追加一条下推关系；按 (from, to) 去重，后写的赢
    （跟 Ontology._merge() 的合并规则一致）。写完清掉 load() 的 lru_cache，
    下一次 load(tenant=profile) 就能看到。"""
    path = ensure_profile(profile)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("tenant", profile)
    links = list(data.get("links") or [])
    links = [link for link in links if not (link.get("from") == source and link.get("to") == target)]
    entry = {"from": source, "to": target, "zh": zh, "verified": "confirmed"}
    links.append(entry)
    data["links"] = links
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    load.cache_clear()
    return entry
