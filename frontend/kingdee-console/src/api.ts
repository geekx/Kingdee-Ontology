import type {
  A2AAuditRow,
  A2AResult,
  Assistant,
  CatalogResponse,
  Conversation,
  Message,
  OntologyGraph,
  Role,
  Tenant,
  ToolCallEvent,
} from './types'

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status} ${path}: ${body}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  catalog: () => req<CatalogResponse>('/catalog'),
  tools: () => req<{ tools: { name: string; description: string }[]; demo_mode: boolean }>('/tools'),
  callTool: (name: string, args: Record<string, unknown>) =>
    req<Record<string, unknown>>(`/tools/${name}/call`, {
      method: 'POST',
      body: JSON.stringify({ args }),
    }),

  tenants: () => req<Tenant[]>('/tenants'),
  createTenant: (name: string, profile = '', env_file = '') =>
    req<Tenant>('/tenants', { method: 'POST', body: JSON.stringify({ name, profile, env_file }) }),

  roles: () => req<Role[]>('/roles'),
  createRole: (name: string, allowed_nouns: string[]) =>
    req<Role>('/roles', { method: 'POST', body: JSON.stringify({ name, allowed_nouns }) }),

  assistants: () => req<Assistant[]>('/assistants'),
  createAssistant: (name: string, tenant_id: string, role_id: string) =>
    req<Assistant>('/assistants', {
      method: 'POST',
      body: JSON.stringify({ name, tenant_id, role_id }),
    }),

  conversations: (assistantId?: string) =>
    req<Conversation[]>(`/conversations${assistantId ? `?assistant_id=${assistantId}` : ''}`),
  createConversation: (assistant_id: string, title = '新对话') =>
    req<Conversation>('/conversations', {
      method: 'POST',
      body: JSON.stringify({ assistant_id, title }),
    }),
  renameConversation: (id: string, title: string) =>
    req<Conversation>(`/conversations/${id}`, { method: 'PATCH', body: JSON.stringify({ title }) }),
  deleteConversation: (id: string) => req<{ ok: boolean }>(`/conversations/${id}`, { method: 'DELETE' }),
  messages: (conversationId: string) => req<Message[]>(`/conversations/${conversationId}/messages`),
  sendMessage: (conversationId: string, content: string) =>
    req<Message>(`/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),

  a2aRequest: (
    from_assistant_id: string,
    to_assistant_id: string,
    verb: string,
    noun: string,
  ) =>
    req<A2AResult>('/a2a/request', {
      method: 'POST',
      body: JSON.stringify({ from_assistant_id, to_assistant_id, verb, noun }),
    }),
  a2aLog: (limit = 100) => req<A2AAuditRow[]>(`/a2a/log?limit=${limit}`),

  ontologyGraph: () => req<OntologyGraph>('/ontology/graph'),
  addOntologyLink: (source: string, target: string, zh: string) =>
    req<unknown>('/ontology/links', { method: 'POST', body: JSON.stringify({ source, target, zh }) }),
}

/** 订阅工具调用事件流——节点流向动效的数据源。断线每 2s 自动重连。 */
export function connectEventStream(onEvent: (event: ToolCallEvent) => void): () => void {
  let ws: WebSocket | null = null
  let closed = false
  let retryTimer: ReturnType<typeof setTimeout> | null = null

  const connect = () => {
    if (closed) return
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${window.location.host}/api/events/stream`)
    ws.onmessage = (ev) => {
      try {
        onEvent(JSON.parse(ev.data) as ToolCallEvent)
      } catch {
        // 忽略解析不出来的消息，不影响其它事件
      }
    }
    ws.onclose = () => {
      if (!closed) retryTimer = setTimeout(connect, 2000)
    }
  }
  connect()

  return () => {
    closed = true
    if (retryTimer) clearTimeout(retryTimer)
    ws?.close()
  }
}
