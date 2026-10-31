"""控制台自己的持久化 —— 租户/角色/助理/对话/消息/A2A 审计。

跟金蝶账套完全无关的"控制台元数据"用一个 sqlite 文件存，默认放在
当前目录下的 kingdee_console.db（可用 KINGDEE_CONSOLE_DB 覆盖），
跟 kingdee_ontology 自己的 operation_audit.jsonl 是两套互不干扰的东西。
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    profile TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    allowed_nouns TEXT NOT NULL DEFAULT '[]',   -- JSON 数组：form_id 列表
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS assistants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tenant_id TEXT NOT NULL REFERENCES tenants(id),
    role_id TEXT NOT NULL REFERENCES roles(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    assistant_id TEXT NOT NULL REFERENCES assistants(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,                  -- user | assistant
    content TEXT NOT NULL DEFAULT '',
    capability_tags TEXT NOT NULL DEFAULT '[]',   -- JSON：CapabilityTag 列表
    tool_calls TEXT NOT NULL DEFAULT '[]',        -- JSON：[{tool, args, result}]
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS a2a_audit (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    from_assistant_id TEXT NOT NULL,
    to_assistant_id TEXT NOT NULL,
    verb TEXT NOT NULL,
    noun TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def db_path() -> Path:
    return Path(os.environ.get("KINGDEE_CONSOLE_DB", "kingdee_console.db"))


_initialized_paths: set[str] = set()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = db_path()
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    key = str(path.resolve())
    if key not in _initialized_paths:
        conn.executescript(SCHEMA)
        conn.commit()
        _initialized_paths.add(key)
    try:
        yield conn
    finally:
        conn.close()


def reset_cache() -> None:
    """测试用：换了 KINGDEE_CONSOLE_DB 之后强制下一次 connect() 重新建表。"""
    _initialized_paths.clear()
