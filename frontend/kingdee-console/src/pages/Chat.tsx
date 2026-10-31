import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { CapabilityChip } from '../components/CapabilityChip'
import type { Assistant, Conversation, Message } from '../types'

function Sidebar({
  assistants,
  assistantId,
  setAssistantId,
  conversations,
  activeId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
}: {
  assistants: Assistant[]
  assistantId: string
  setAssistantId: (id: string) => void
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onCreate: () => void
  onRename: (id: string, title: string) => void
  onDelete: (id: string) => void
}) {
  return (
    <aside className="flex w-72 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="p-3">
        <label className="mb-1 block text-xs font-medium text-slate-400">当前助理</label>
        <select
          className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-800"
          value={assistantId}
          onChange={(e) => setAssistantId(e.target.value)}
        >
          {assistants.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-xs font-medium text-slate-400">对话历史</span>
        <button
          className="rounded bg-slate-900 px-2 py-1 text-xs text-white dark:bg-slate-100 dark:text-slate-900"
          onClick={onCreate}
        >
          + 新对话
        </button>
      </div>
      <ul className="flex-1 space-y-1 overflow-y-auto px-2">
        {conversations.map((c) => (
          <li
            key={c.id}
            className={`group flex items-center justify-between rounded-lg px-2 py-1.5 text-sm ${
              c.id === activeId
                ? 'bg-slate-100 dark:bg-slate-800'
                : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
            }`}
          >
            <button
              className="flex-1 truncate text-left"
              onClick={() => onSelect(c.id)}
              title={c.title}
            >
              {c.title || '新对话'}
            </button>
            <div className="hidden gap-1 group-hover:flex">
              <button
                className="text-slate-400 hover:text-slate-700"
                onClick={() => {
                  const title = window.prompt('重命名对话', c.title)
                  if (title) onRename(c.id, title)
                }}
              >
                ✎
              </button>
              <button className="text-slate-400 hover:text-red-600" onClick={() => onDelete(c.id)}>
                ✕
              </button>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-xl rounded-2xl px-4 py-3 text-sm ${
          isUser
            ? 'bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900'
            : 'bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-slate-100'
        }`}
      >
        {!isUser && message.capability_tags.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {message.capability_tags.map((tag, i) => (
              <CapabilityChip key={`${tag.verb}-${tag.noun}-${i}`} tag={tag} />
            ))}
          </div>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  )
}

export function Chat() {
  const [assistants, setAssistants] = useState<Assistant[]>([])
  const [assistantId, setAssistantId] = useState('')
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.assistants().then((list) => {
      setAssistants(list)
      if (list.length > 0) setAssistantId(list[0].id)
    })
  }, [])

  useEffect(() => {
    if (!assistantId) return
    api.conversations(assistantId).then((list) => {
      setConversations(list)
      setActiveId(list[0]?.id ?? null)
    })
  }, [assistantId])

  useEffect(() => {
    if (!activeId) {
      setMessages([])
      return
    }
    api.messages(activeId).then(setMessages)
  }, [activeId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const createConversation = async () => {
    const conv = await api.createConversation(assistantId)
    setConversations((prev) => [conv, ...prev])
    setActiveId(conv.id)
  }

  const send = async () => {
    if (!input.trim() || !activeId || sending) return
    const text = input.trim()
    setInput('')
    setMessages((prev) => [
      ...prev,
      {
        id: `tmp-${Date.now()}`,
        conversation_id: activeId,
        role: 'user',
        content: text,
        capability_tags: [],
        tool_calls: [],
        created_at: '',
      },
    ])
    setSending(true)
    try {
      const reply = await api.sendMessage(activeId, text)
      setMessages((prev) => [...prev, reply])
      setConversations(await api.conversations(assistantId))
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          conversation_id: activeId,
          role: 'assistant',
          content: `发送失败：${err instanceof Error ? err.message : String(err)}`,
          capability_tags: [],
          tool_calls: [],
          created_at: '',
        },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-57px)]">
      <Sidebar
        assistants={assistants}
        assistantId={assistantId}
        setAssistantId={setAssistantId}
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onCreate={createConversation}
        onRename={async (id, title) => {
          await api.renameConversation(id, title)
          setConversations(await api.conversations(assistantId))
        }}
        onDelete={async (id) => {
          await api.deleteConversation(id)
          const list = await api.conversations(assistantId)
          setConversations(list)
          if (id === activeId) setActiveId(list[0]?.id ?? null)
        }}
      />
      <div className="flex flex-1 flex-col">
        <div className="flex-1 space-y-3 overflow-y-auto p-6">
          {messages.length === 0 && (
            <p className="text-sm text-slate-400">
              试试输入"查一下库存"——回复里会按业务类别给调用的能力上色。
            </p>
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
          {sending && <p className="text-sm text-slate-400">正在思考…</p>}
          <div ref={bottomRef} />
        </div>
        <div className="border-t border-slate-200 p-4 dark:border-slate-800">
          <div className="flex gap-2">
            <input
              className="flex-1 rounded-full border border-slate-300 px-4 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
              placeholder={activeId ? '输入消息…' : '先新建一个对话'}
              value={input}
              disabled={!activeId}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') send()
              }}
            />
            <button
              className="rounded-full bg-slate-900 px-5 py-2 text-sm text-white disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900"
              disabled={!activeId || sending}
              onClick={send}
            >
              发送
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
