"""能力目录 —— 把本体注册表变成 Dashboard/对话界面都能用的"上色后的能力"。

用户的原话："在对话界面将已有的能力标上颜色，比如我要查库存，那么查库存
对应发送时，整理成包含schema语义工具的能力"。

实现选择：**不**为每个 (verb, noun) 组合生成一个独立的 Claude 工具——
那正是底座从 97 个专用工具收敛成 11 个通用工具之前的老路，会把刚省下来的
token 又加回去。Claude 仍然只看 kd_query/kd_act 等 11 个通用工具；
语义化的"能力标签"是**执行后**从 Dispatcher 真实返回的 verb/noun 反推出来的
（kd_query/kd_act 的返回体本来就带 noun/zh/category，见 base/dispatch.py），
颜色只是这份语义标签在 UI 上的呈现方式。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from kingdee_ontology.base.ontology import Ontology

# 按名词类别上色 —— 与 base/ontology.py 的 Noun.category 对齐
CATEGORY_COLORS: dict[str, dict[str, str]] = {
    "bill":        {"bg": "#dbeafe", "fg": "#1d4ed8", "border": "#93c5fd", "label": "单据"},
    "master_data": {"bg": "#dcfce7", "fg": "#15803d", "border": "#86efac", "label": "基础资料"},
    "view":        {"bg": "#f3e8ff", "fg": "#7e22ce", "border": "#d8b4fe", "label": "视图/查询"},
    "system":      {"bg": "#f1f5f9", "fg": "#475569", "border": "#cbd5e1", "label": "系统对象"},
}
DEFAULT_COLOR = {"bg": "#f1f5f9", "fg": "#475569", "border": "#cbd5e1", "label": "其他"}
# 写动词额外加一个强调色——不管名词类别是什么，"会改数据"这件事本身要显眼
WRITE_ACCENT = "#dc2626"


def color_for_category(category: str) -> dict[str, str]:
    return CATEGORY_COLORS.get(category, DEFAULT_COLOR)


@dataclass(frozen=True)
class CapabilityTag:
    """对话界面里挂在一条消息上的"能力 chip"。"""

    verb: str
    verb_zh: str
    noun: str
    noun_zh: str
    category: str
    category_label: str
    color: dict[str, str]
    destructive: bool = False
    kind: str = "read"            # read | write

    def to_dict(self) -> dict[str, Any]:
        return {
            "verb": self.verb, "verb_zh": self.verb_zh,
            "noun": self.noun, "noun_zh": self.noun_zh,
            "category": self.category, "category_label": self.category_label,
            "color": self.color, "destructive": self.destructive, "kind": self.kind,
        }


def tag_for(ontology: Ontology, verb_name: str, noun_form_id: str) -> Optional[CapabilityTag]:
    """从一次真实的 kd_query/kd_act 调用反推出一个能力标签。查不到就返回 None
    （比如系统端点、或名词在合并查询报了错），调用方据此跳过，不强行拼一个假标签。
    """
    v = ontology.verbs.get(verb_name)
    n = ontology.nouns.get(noun_form_id)
    if v is None or n is None:
        return None
    return CapabilityTag(
        verb=v.name, verb_zh=v.zh, noun=n.form_id, noun_zh=n.zh,
        category=n.category, category_label=color_for_category(n.category)["label"],
        color=color_for_category(n.category), destructive=v.destructive, kind=v.kind,
    )


def tags_from_dispatch_result(ontology: Ontology, tool: str, result: dict) -> list[CapabilityTag]:
    """从 kd_query/kd_act/kd_push/kd_read 的返回体里抽出全部能力标签。

    kd_query 合并查询（逗号分隔多个名词）时返回体里是 result["groups"]，
    每组各自带 noun；单一名词查询则顶层直接带 noun。act/push 恒定顶层带
    verb+noun。按工具名决定怎么找 verb——返回体本身不带 verb 字样的只有
    query/read（它们的 verb 就是工具名去掉 kd_ 前缀）。
    """
    verb_of_tool = {"kd_query": "query", "kd_read": "read"}
    tags: list[CapabilityTag] = []
    groups = result.get("groups") if isinstance(result, dict) else None
    if isinstance(groups, list):
        for g in groups:
            if isinstance(g, dict) and "noun" in g and "error" not in g:
                verb = verb_of_tool.get(tool, result.get("verb", ""))
                t = tag_for(ontology, verb, g["noun"])
                if t:
                    tags.append(t)
        return tags
    if isinstance(result, dict) and "noun" in result:
        verb = result.get("verb") or verb_of_tool.get(tool, "")
        if verb:
            t = tag_for(ontology, verb, result["noun"])
            if t:
                tags.append(t)
    return tags


@dataclass(frozen=True)
class CapabilityEntry:
    """Dashboard 的"能力矩阵"里一行：某个名词能做哪个动词。"""

    verb: str
    verb_zh: str
    kind: str
    noun: str
    noun_zh: str
    category: str
    color: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": f"{self.verb}:{self.noun}", "verb": self.verb, "verb_zh": self.verb_zh,
            "kind": self.kind, "noun": self.noun, "noun_zh": self.noun_zh,
            "category": self.category, "color": self.color,
        }


def full_catalog(ontology: Ontology) -> list[CapabilityEntry]:
    """整个本体的能力矩阵：每个名词 × 它允许的每个动词，各一条。"""
    out: list[CapabilityEntry] = []
    for n in ontology.nouns.values():
        color = color_for_category(n.category)
        for verb_name in sorted(n.allowed_verbs):
            v = ontology.verbs.get(verb_name)
            if v is None:
                continue
            out.append(CapabilityEntry(
                verb=v.name, verb_zh=v.zh, kind=v.kind,
                noun=n.form_id, noun_zh=n.zh, category=n.category, color=color,
            ))
    out.sort(key=lambda e: (e.category, e.noun, e.verb))
    return out


def catalog_summary(ontology: Ontology) -> dict[str, Any]:
    """Dashboard 顶部的统计卡片：按类别、按读写分别计数。"""
    entries = full_catalog(ontology)
    by_category: dict[str, int] = {}
    by_kind = {"read": 0, "write": 0}
    for e in entries:
        by_category[e.category] = by_category.get(e.category, 0) + 1
        by_kind[e.kind] = by_kind.get(e.kind, 0) + 1
    return {
        "total_capabilities": len(entries),
        "total_nouns": len(ontology.nouns),
        "total_verbs": len(ontology.verbs),
        "by_category": by_category,
        "by_kind": by_kind,
    }
