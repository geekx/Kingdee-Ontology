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
  env_file: string
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

export interface OntologyNode {
  id: string
  label: string
  category: string
  color: Color
  allowed_verbs: string[]
}

export interface OntologyEdge {
  id: string
  source: string
  target: string
  label: string
  verified: string
}

export interface OntologyVerb {
  name: string
  zh: string
  kind: 'read' | 'write'
}

export interface OntologyGraph {
  nodes: OntologyNode[]
  edges: OntologyEdge[]
  verbs: OntologyVerb[]
  categories: string[]
  active_profile: string
}

export interface ObjectCardProperty {
  name: string
  is_lookup: boolean
  base: string
  value?: unknown
}

export interface ObjectCardAction {
  verb: string
  zh: string
  object_type: string
  params: { name: string; type: string; required: boolean; label: string; hint?: string }[]
  requires_state: string[]
  to_state: string | null
  atomicity: string
  idempotent: boolean
  inverse: string | null
  destructive: boolean
  needs_confirmation: boolean
  enabled: boolean
  reason?: string
  unverified?: boolean
  note?: string
}

export interface ObjectCardLink {
  name: string
  direction: 'outgoing' | 'incoming'
  kind: string
  target_type: string
  target_zh: string
  verified: string
  note: string
}

export interface ObjectCardOperation {
  key: string
  zh: string
  owner: string
  desc: string
  steps: number
  starts_here: boolean
}

export interface ObjectCardState {
  code: string
  zh: string
}

export interface ObjectCard {
  object_type: string
  zh: string
  category: string
  is_instance: boolean
  id: string | null
  title: string | null
  state: string | null
  state_zh: string | null
  properties: ObjectCardProperty[]
  actions: ObjectCardAction[]
  links: ObjectCardLink[]
  operations: ObjectCardOperation[]
  states: ObjectCardState[]
  selected_state: string | null
}

export interface ToolCallEvent {
  tool: string
  source: 'chat' | 'direct' | 'a2a'
  capability_tags: CapabilityTag[]
  ok: boolean
  at: number
}
