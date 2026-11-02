import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, connectEventStream } from '../api'
import type { OntologyGraph, OntologyNode, ToolCallEvent } from '../types'

const CATEGORY_ORDER = ['bill', 'master_data', 'view', 'system']
const COL_W = 210
const ROW_H = 64
const BLOCK_GAP = 90
const MAX_COLS = 5
const PULSE_MS = 1700

function layout(nodes: OntologyNode[]): Record<string, { x: number; y: number }> {
  const byCategory: Record<string, OntologyNode[]> = {}
  for (const n of nodes) {
    ;(byCategory[n.category] ??= []).push(n)
  }
  const positions: Record<string, { x: number; y: number }> = {}
  let xOffset = 0
  for (const cat of CATEGORY_ORDER) {
    const list = byCategory[cat] ?? []
    if (list.length === 0) continue
    const cols = Math.min(MAX_COLS, Math.max(1, Math.ceil(Math.sqrt(list.length))))
    list.forEach((n, i) => {
      const col = i % cols
      const row = Math.floor(i / cols)
      positions[n.id] = { x: xOffset + col * COL_W, y: row * ROW_H }
    })
    xOffset += cols * COL_W + BLOCK_GAP
  }
  return positions
}

function EditorPanel({ nodes, onAdded }: { nodes: OntologyNode[]; onAdded: () => void }) {
  const [source, setSource] = useState('')
  const [target, setTarget] = useState('')
  const [zh, setZh] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const sorted = useMemo(() => [...nodes].sort((a, b) => a.label.localeCompare(b.label)), [nodes])

  const submit = async () => {
    if (!source || !target) return
    setBusy(true)
    setError('')
    try {
      await api.addOntologyLink(source, target, zh)
      setZh('')
      onAdded()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h4 className="mb-2 font-semibold">节点编辑器：新增下推关系</h4>
      <p className="mb-3 text-xs text-slate-500">
        写进当前 profile 覆盖层，不改底座 registry.yml；节点可以直接拖拽摆放。
      </p>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <select
          className="rounded border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-800"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        >
          <option value="">源单…</option>
          {sorted.map((n) => (
            <option key={n.id} value={n.id}>
              {n.label}（{n.id}）
            </option>
          ))}
        </select>
        <span>→</span>
        <select
          className="rounded border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-800"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
        >
          <option value="">目标单…</option>
          {sorted.map((n) => (
            <option key={n.id} value={n.id}>
              {n.label}（{n.id}）
            </option>
          ))}
        </select>
        <input
          className="min-w-40 flex-1 rounded border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-800"
          placeholder="说明（留空自动生成）"
          value={zh}
          onChange={(e) => setZh(e.target.value)}
        />
        <button
          className="rounded bg-slate-900 px-3 py-1 text-white disabled:opacity-40 dark:bg-slate-100 dark:text-slate-900"
          disabled={!source || !target || busy}
          onClick={submit}
        >
          添加
        </button>
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  )
}

export function Ontology() {
  const [graph, setGraph] = useState<OntologyGraph | null>(null);
  const [activeNodes, setActiveNodes] = useState<Map<string, number>>(new Map());
  const [activeEdges, setActiveEdges] = useState<Map<string, number>>(new Map());
  const timers = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());

  const loadGraph = () => {
    api.ontologyGraph().then(setGraph)
  }

  useEffect(loadGraph, [])

  useEffect(() => {
    const pulse = (kind: 'node' | 'edge', id: string) => {
      const setter = kind === 'node' ? setActiveNodes : setActiveEdges
      const token = Date.now()
      setter((prev) => new Map(prev).set(id, token))
      const t = setTimeout(() => {
        setter((prev) => {
          if (prev.get(id) !== token) return prev   // 这期间又被新事件点亮过，别提前灭掉
          const next = new Map(prev)
          next.delete(id)
          return next
        })
      }, PULSE_MS)
      timers.current.add(t)
    }

    const onEvent = (event: ToolCallEvent) => {
      const nouns = [...new Set(event.capability_tags.map((t) => t.noun))]
      for (const noun of nouns) pulse('node', noun)
      const pushTags = event.capability_tags.filter((t) => t.verb === 'push')
      if (pushTags.length === 2) {
        pulse('edge', `${pushTags[0].noun}->${pushTags[1].noun}`)
      }
    }

    const disconnect = connectEventStream(onEvent)
    const timerSet = timers.current
    return () => {
      disconnect()
      for (const t of timerSet) clearTimeout(t)
    }
  }, [])

  const { nodes, edges } = useMemo<{ nodes: Node[]; edges: Edge[] }>(() => {
    if (!graph) return { nodes: [], edges: [] }
    const positions = layout(graph.nodes)
    const nodes: Node[] = graph.nodes.map((n) => {
      const active = activeNodes.has(n.id)
      return {
        id: n.id,
        position: positions[n.id] ?? { x: 0, y: 0 },
        data: { label: `${n.label}` },
        style: {
          background: n.color.bg,
          color: n.color.fg,
          border: `2px solid ${active ? '#f97316' : n.color.border}`,
          borderRadius: 10,
          padding: '6px 10px',
          fontSize: 12,
          width: 180,
          boxShadow: active ? '0 0 0 4px rgba(249,115,22,0.35)' : undefined,
          transition: 'box-shadow 200ms ease, border-color 200ms ease',
        },
      }
    })
    const baseEdgeIds = new Set(graph.edges.map((e) => e.id))
    const edges: Edge[] = graph.edges.map((e) => {
      const active = activeEdges.has(e.id)
      return {
        id: e.id, source: e.source, target: e.target, label: e.label,
        animated: active,
        style: {
          stroke: active ? '#f97316' : e.verified === 'suspect' ? '#cbd5e1' : '#64748b',
          strokeWidth: active ? 3 : 1.5,
          strokeDasharray: e.verified === 'suspect' ? '4 3' : undefined,
        },
        labelStyle: { fontSize: 10 },
      }
    })
    // 动效边里，可能有一条"这次调用正在走"的 from→to 关系根本没登记在 links 里
    // （比如临时自定义的下推）——临时补一条虚拟边，调用结束自动消失。
    for (const id of activeEdges.keys()) {
      if (!baseEdgeIds.has(id)) {
        const [source, target] = id.split('->')
        if (source && target) {
          edges.push({
            id, source, target, animated: true,
            style: { stroke: '#f97316', strokeWidth: 3 },
          })
        }
      }
    }
    return { nodes, edges }
  }, [graph, activeNodes, activeEdges])

  if (!graph) {
    return <div className="p-6 text-slate-400">加载中…</div>
  }

  return (
    <div className="flex h-[calc(100vh-57px)] flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Ontology 图谱</h1>
          <p className="text-xs text-slate-500">
            {graph.nodes.length} 个名词 · {graph.edges.length} 条下推关系 · 活跃 profile：
            {graph.active_profile}
          </p>
        </div>
        <p className="text-xs text-slate-400">橙色高亮 = 最近 ~1.7s 内被调用（对话/直接调用/A2A 都算）</p>
      </div>

      <EditorPanel nodes={graph.nodes} onAdded={loadGraph} />

      <div className="flex-1 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800">
        <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
          <Background />
          <Controls />
          <MiniMap pannable zoomable />
        </ReactFlow>
      </div>
    </div>
  )
}
