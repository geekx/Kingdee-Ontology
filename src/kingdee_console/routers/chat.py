"""对话窗口 API —— 发消息（走意图识别）+ 对话记录管理。"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from kingdee_console import conversations as conv
from kingdee_console import tenancy
from kingdee_console.gateway import default_gateway
from kingdee_console.intent import IntentEngine

router = APIRouter(prefix="/api/conversations", tags=["chat"])


class CreateConversationInput(BaseModel):
    assistant_id: str
    title: str = "新对话"


@router.post("")
async def create_conversation(body: CreateConversationInput) -> dict[str, Any]:
    if tenancy.get_assistant(body.assistant_id) is None:
        raise HTTPException(status_code=404, detail="助理不存在")
    return conv.create_conversation(body.assistant_id, body.title).to_dict()


@router.get("")
async def list_conversations(assistant_id: Optional[str] = None) -> list[dict[str, Any]]:
    return [c.to_dict() for c in conv.list_conversations(assistant_id)]


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str) -> dict[str, Any]:
    c = conv.get_conversation(conversation_id)
    if c is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    return c.to_dict()


class RenameInput(BaseModel):
    title: str


@router.patch("/{conversation_id}")
async def rename_conversation(conversation_id: str, body: RenameInput) -> dict[str, Any]:
    if conv.get_conversation(conversation_id) is None:
        raise HTTPException(status_code=404, detail="对话不存在")
    conv.rename_conversation(conversation_id, body.title)
    return conv.get_conversation(conversation_id).to_dict()


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str) -> dict[str, Any]:
    conv.delete_conversation(conversation_id)
    return {"ok": True}


@router.get("/{conversation_id}/messages")
async def list_messages(conversation_id: str) -> list[dict[str, Any]]:
    return [m.to_dict() for m in conv.list_messages(conversation_id)]


class SendMessageInput(BaseModel):
    content: str


@router.post("/{conversation_id}/messages")
async def send_message(conversation_id: str, body: SendMessageInput) -> dict[str, Any]:
    c = conv.get_conversation(conversation_id)
    if c is None:
        raise HTTPException(status_code=404, detail="对话不存在")

    conv.add_message(conversation_id, "user", body.content)

    history = [{"role": m.role, "content": m.content} for m in conv.list_messages(conversation_id)
               if m.role in ("user", "assistant")][:-1]   # 不含刚写进去的这条，由 resolve() 自己补

    engine = IntentEngine(gateway=default_gateway())
    try:
        outcome = await engine.resolve(body.content, history=history)
    except Exception as e:
        # 意图识别失败（常见原因：没配 ANTHROPIC_API_KEY）不该把整个会话
        # 搞成一个干巴巴的 500——把原因直接作为一条助理消息留在对话里，
        # 用户看得懂出了什么问题，Dashboard 的直接调用面板仍然可用。
        from kingdee_console.intent import IntentResult
        outcome = IntentResult(text=f"意图识别暂时不可用：{type(e).__name__}: {e}")

    all_tags = [t for inv in outcome.invocations for t in inv.capability_tags]
    assistant_msg = conv.add_message(
        conversation_id, "assistant", outcome.text,
        capability_tags=all_tags,
        tool_calls=[inv.to_dict() for inv in outcome.invocations],
    )
    return assistant_msg.to_dict()
