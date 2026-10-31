"""对话和对话记录管理 —— 持久化在 db.py 的 sqlite 里。

每个会话（Conversation）挂在某个助理（Assistant）名下：助理决定了
这个会话里能调用哪些能力（RBAC，见 tenancy.py），对话历史本身只是
消息列表 + 每条 assistant 消息带的能力标签（capability_tags）。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from kingdee_console.db import connect


@dataclass
class Message:
    id: str
    conversation_id: str
    role: str                      # user | assistant
    content: str
    capability_tags: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "conversation_id": self.conversation_id, "role": self.role,
                "content": self.content, "capability_tags": self.capability_tags,
                "tool_calls": self.tool_calls, "created_at": self.created_at}


@dataclass
class Conversation:
    id: str
    title: str
    assistant_id: str
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "title": self.title, "assistant_id": self.assistant_id,
                "created_at": self.created_at, "updated_at": self.updated_at}


def create_conversation(assistant_id: str, title: str = "新对话") -> Conversation:
    cid = str(uuid.uuid4())
    with connect() as c:
        c.execute("INSERT INTO conversations (id, title, assistant_id) VALUES (?, ?, ?)",
                  (cid, title, assistant_id))
        c.commit()
        row = c.execute("SELECT * FROM conversations WHERE id = ?", (cid,)).fetchone()
    return _conv_from_row(row)


def list_conversations(assistant_id: Optional[str] = None) -> list[Conversation]:
    with connect() as c:
        if assistant_id:
            rows = c.execute(
                "SELECT * FROM conversations WHERE assistant_id = ? ORDER BY updated_at DESC",
                (assistant_id,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM conversations ORDER BY updated_at DESC").fetchall()
    return [_conv_from_row(r) for r in rows]


def get_conversation(conversation_id: str) -> Optional[Conversation]:
    with connect() as c:
        row = c.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return _conv_from_row(row) if row else None


def rename_conversation(conversation_id: str, title: str) -> None:
    with connect() as c:
        c.execute("UPDATE conversations SET title = ?, updated_at = datetime('now') WHERE id = ?",
                  (title, conversation_id))
        c.commit()


def delete_conversation(conversation_id: str) -> None:
    with connect() as c:
        c.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        c.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        c.commit()


def add_message(conversation_id: str, role: str, content: str,
                capability_tags: Optional[list[dict]] = None,
                tool_calls: Optional[list[dict]] = None) -> Message:
    mid = str(uuid.uuid4())
    with connect() as c:
        c.execute(
            "INSERT INTO messages (id, conversation_id, role, content, capability_tags, "
            "tool_calls) VALUES (?, ?, ?, ?, ?, ?)",
            (mid, conversation_id, role, content,
             json.dumps(capability_tags or [], ensure_ascii=False),
             json.dumps(tool_calls or [], ensure_ascii=False)))
        c.execute("UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
                  (conversation_id,))
        c.commit()
        row = c.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
    return _msg_from_row(row)


def list_messages(conversation_id: str) -> list[Message]:
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
            (conversation_id,)).fetchall()
    return [_msg_from_row(r) for r in rows]


def _conv_from_row(row) -> Conversation:
    return Conversation(id=row["id"], title=row["title"], assistant_id=row["assistant_id"],
                        created_at=row["created_at"], updated_at=row["updated_at"])


def _msg_from_row(row) -> Message:
    return Message(id=row["id"], conversation_id=row["conversation_id"], role=row["role"],
                   content=row["content"], capability_tags=json.loads(row["capability_tags"]),
                   tool_calls=json.loads(row["tool_calls"]), created_at=row["created_at"])
