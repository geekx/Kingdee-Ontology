"""Ontology 节点编辑器的持久化 —— 往"活跃 profile"的覆盖层追加自定义
名词（二开表单）和下推关系。

不碰底座 registry.yml（共享基础设施，谁都不该从 Web UI 改它，改错一条
影响的是所有租户），只写 profiles/<profile>/profile.yml 的覆盖层——
跟 Ontology._merge() 的既有设计完全对齐：profile 只能新增/改写底座条目，
不能删除（见 base/ontology.py 的 Ontology.__init__ 说明）。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml

from kingdee_ontology.base.ontology import load

DEMO_PROFILE = "console-demo"

# 复用 catalog.py 的类别集合（单一事实来源）——新增名词时类别必须落在
# 这几个之一，否则 UI 上色会退化成灰色默认值，且语义上也没意义。
from kingdee_console.catalog import CATEGORY_COLORS  # noqa: E402

VALID_CATEGORIES = frozenset(CATEGORY_COLORS.keys())


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


def add_noun(profile: str, form_id: str, zh: str, category: str, allowed_verbs: list[str],
            alias: Optional[list[str]] = None, default_fields: str = "") -> dict[str, Any]:
    """往 profile 的 nouns 段新增/改写一个名词定义；不碰底座 registry.yml。

    跟 Ontology._merge() 的合并规则对齐：form_id 若已在底座里存在，这里
    写的字段会覆盖同名字段，其余字段（这个表单的其它属性，比如底座已有的
    default_fields）保留底座原值——这正是 profile 系统设计给"只改一两个
    字段"用的（见 profiles/README.md 的例子）；form_id 若不存在，就是
    注册了一个全新的二开表单。写完清掉 load() 的 lru_cache，下一次
    load(tenant=profile) 就能看到。
    """
    path = ensure_profile(profile)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    data.setdefault("tenant", profile)
    nouns = dict(data.get("nouns") or {})
    entry: dict[str, Any] = {"zh": zh, "category": category, "allowed_verbs": list(allowed_verbs)}
    if alias:
        entry["alias"] = list(alias)
    if default_fields:
        entry["default_fields"] = default_fields
    nouns[form_id] = entry
    data["nouns"] = nouns
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    load.cache_clear()
    return {"form_id": form_id, **entry}


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
