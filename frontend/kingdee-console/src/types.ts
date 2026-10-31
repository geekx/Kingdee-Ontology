export interface Color {
  bg: string
  fg: string
  border: string
  label: string
}

export interface CapabilityTag {
  verb: string
  verb_zh: string
  noun: string
  noun_zh: string
  category: string
  category_label: string
  color: Color
  destructive: boolean
  kind: 'read' | 'write'
}

export interface CapabilityEntry {
  id: string
  verb: string
  verb_zh: string
  kind: 'read' | 'write'
  noun: string
  noun_zh: string
  category: string
  color: Color
}

export interface CatalogSummary {
  total_capabilities: number
  total_nouns: number
  total_verbs: number
  by_category: Record<string, number>
  by_kind: Record<string, number>
}

export interface CatalogResponse {
  summary: CatalogSummary
  entries: CapabilityEntry[]
  demo_mode: boolean
}

export interface Tenant {
  id: string
  name: string
  profile: string
}

export interface Role {
  id: string
  name: string
  allowed_nouns: string[]
}

export interface Assistant {
  id: string
  name: string
  tenant_id: string
  role_id: string
}

export interface Conversation {
  id: string
  title: string
  assistant_id: string
  created_at: string
  updated_at: string
}

export interface ToolCall {
  tool: string
  args: Record<string, unknown>
  result: Record<string, unknown>
  capability_tags: CapabilityTag[]
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  capability_tags: CapabilityTag[]
  tool_calls: ToolCall[]
  created_at: string
}

export interface A2AAuditRow {
  id: string
  trace_id: string
  from_assistant_id: string
  to_assistant_id: string
  verb: string
  noun: string
  allowed: number
  reason: string
  created_at: string
}

export interface A2AResult {
  ok: boolean
  trace_id: string
  reason: string
  result?: Record<string, unknown>
  provenance?: {
    executed_by: string
    executed_by_role: string
    requested_by: string
    capabilities: CapabilityTag[]
  }
}
