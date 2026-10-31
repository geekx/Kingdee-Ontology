import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import type {
  A2AAuditRow,
  Assistant,
  CatalogResponse,
  CapabilityEntry,
  Role,
  Tenant,
} from '../types'

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">{value}</div>
    </div>
  )
}

function CapabilityGrid({ entries }: { entries: CapabilityEntry[] }) {
  const byCategory = useMemo(() => {
    const groups = new Map<string, CapabilityEntry[]>()
    for (const e of entries) {
      const list = groups.get(e.category) ?? []
      list.push(e)
      groups.set(e.category, list)
    }
    return groups
  }, [entries])

  return (
    <div className="space-y-6">
      {[...byCategory.entries()].map(([category, list]) => (
        <div key={category}>
          <h3
            className="mb-2 inline-block rounded-md px-2 py-0.5 text-sm font-semibold"
            style={{ backgroundColor: list[0].color.bg, color: list[0].color.fg }}
          >
            {list[0].color.label}（{list.length}）
          </h3>
          <div className="flex flex-wrap gap-2">
            {list.map((e) => (
              <span
                key={e.id}
                className="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs"
                style={{ backgroundColor: e.color.bg, color: e.color.fg, borderColor: e.color.border }}
                title={e.noun}
              >
                {e.kind === 'write' && <span className="h-1.5 w-1.5 rounded-full bg-red-600" />}
                {e.verb_zh}·{e.noun_zh}
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function TenancyPanel({
  tenants,
  roles,
  assistants,
  onChanged,
}: {
  tenants: Tenant[]
  roles: Role[]
  assistants: Assistant[]
  onChanged: () => void
}) {
  const [newTenant, setNewTenant] = useState('')
  const [newRole, setNewRole] = useState('')
  const [newRoleNouns, setNewRoleNouns] = useState('')

  const tenantName = (id: string) => tenants.find((t) => t.id === id)?.name ?? id
  const roleName = (id: string) => roles.find((r) => r.id === id)?.name ?? id

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h4 className="mb-2 font-semibold">租户</h4>
        <ul className="mb-3 space-y-1 text-sm">
          {tenants.map((t) => (
            <li key={t.id}>
              {t.name} <span className="text-slate-400">({t.profile || '默认'})</span>
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <input
            className="w-full rounded border border-slate-300 px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-800"
            placeholder="新租户名"
            value={newTenant}
            onChange={(e) => setNewTenant(e.target.value)}
          />
          <button
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white dark:bg-slate-100 dark:text-slate-900"
            onClick={async () => {
              if (!newTenant.trim()) return
              await api.createTenant(newTenant.trim())
              setNewTenant('')
              onChanged()
            }}
          >
            新建
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h4 className="mb-2 font-semibold">角色（业务归口权限）</h4>
        <ul className="mb-3 space-y-1 text-sm">
          {roles.map((r) => (
            <li key={r.id}>
              {r.name}：<span className="text-slate-500">{r.allowed_nouns.join(', ') || '无'}</span>
            </li>
          ))}
        </ul>
        <div className="flex flex-col gap-2">
          <input
            className="rounded border border-slate-300 px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-800"
            placeholder="角色名"
            value={newRole}
            onChange={(e) => setNewRole(e.target.value)}
          />
          <input
            className="rounded border border-slate-300 px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-800"
            placeholder="允许的名词，逗号分隔，如 SAL_SaleOrder"
            value={newRoleNouns}
            onChange={(e) => setNewRoleNouns(e.target.value)}
          />
          <button
            className="rounded bg-slate-900 px-3 py-1 text-sm text-white dark:bg-slate-100 dark:text-slate-900"
            onClick={async () => {
              if (!newRole.trim()) return
              await api.createRole(
                newRole.trim(),
                newRoleNouns.split(',').map((s) => s.trim()).filter(Boolean),
              )
              setNewRole('')
              setNewRoleNouns('')
              onChanged()
            }}
          >
            新建
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <h4 className="mb-2 font-semibold">助理</h4>
        <ul className="space-y-1 text-sm">
          {assistants.map((a) => (
            <li key={a.id}>
              {a.name} —— {tenantName(a.tenant_id)} / {roleName(a.role_id)}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function A2APanel({ assistants }: { assistants: Assistant[] }) {
  const [log, setLog] = useState<A2AAuditRow[]>([])
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [noun, setNoun] = useState('库存')
  const [outcome, setOutcome] = useState<string>('')

  useEffect(() => {
    api.a2aLog().then(setLog)
    if (assistants.length >= 2) {
      setFrom(assistants[0].id)
      setTo(assistants[1].id)
    }
  }, [assistants])

  const nameOf = (id: string) => assistants.find((a) => a.id === id)?.name ?? id

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h4 className="mb-2 font-semibold">A2A 跨助理请求 demo</h4>
      <p className="mb-3 text-sm text-slate-500">
        发起助理问另一个助理要它业务归口下的数据——权限按"被问的那个助理"的角色判断。
      </p>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
        <select
          className="rounded border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-800"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
        >
          {assistants.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <span>问</span>
        <select
          className="rounded border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-800"
          value={to}
          onChange={(e) => setTo(e.target.value)}
        >
          {assistants.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <span>要</span>
        <input
          className="w-32 rounded border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-800"
          value={noun}
          onChange={(e) => setNoun(e.target.value)}
        />
        <span>的数据</span>
        <button
          className="rounded bg-slate-900 px-3 py-1 text-white dark:bg-slate-100 dark:text-slate-900"
          onClick={async () => {
            const r = await api.a2aRequest(from, to, 'query', noun)
            setOutcome(r.ok ? `成功：由 ${r.provenance?.executed_by} 执行` : `拒绝：${r.reason}`)
            setLog(await api.a2aLog())
          }}
        >
          发起请求
        </button>
      </div>
      {outcome && <div className="mb-3 text-sm font-medium">{outcome}</div>}
      <table className="w-full text-left text-xs">
        <thead className="text-slate-400">
          <tr>
            <th className="py-1">时间</th>
            <th>从</th>
            <th>到</th>
            <th>能力</th>
            <th>结果</th>
            <th>原因</th>
          </tr>
        </thead>
        <tbody>
          {log.map((row) => (
            <tr key={row.id} className="border-t border-slate-100 dark:border-slate-800">
              <td className="py-1">{row.created_at}</td>
              <td>{nameOf(row.from_assistant_id)}</td>
              <td>{nameOf(row.to_assistant_id)}</td>
              <td>
                {row.verb}:{row.noun}
              </td>
              <td className={row.allowed ? 'text-emerald-600' : 'text-red-600'}>
                {row.allowed ? '允许' : '拒绝'}
              </td>
              <td className="text-slate-500">{row.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Dashboard() {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null)
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [assistants, setAssistants] = useState<Assistant[]>([])

  const refresh = () => {
    api.catalog().then(setCatalog)
    api.tenants().then(setTenants)
    api.roles().then(setRoles)
    api.assistants().then(setAssistants)
  }

  useEffect(refresh, [])

  if (!catalog) {
    return <div className="p-6 text-slate-400">加载中…</div>
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-6">
      <div>
        <h1 className="text-2xl font-bold">能力总览</h1>
        {catalog.demo_mode && (
          <p className="mt-1 text-sm text-amber-600">
            演示模式：未连真实金蝶账套，数据来自内置示例（FakeTransport）。
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <StatCard label="能力总数" value={catalog.summary.total_capabilities} />
        <StatCard label="名词" value={catalog.summary.total_nouns} />
        <StatCard label="动词" value={catalog.summary.total_verbs} />
        <StatCard label="只读能力" value={catalog.summary.by_kind.read ?? 0} />
        <StatCard label="写操作能力" value={catalog.summary.by_kind.write ?? 0} />
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold">能力矩阵（按业务类别上色）</h2>
        <CapabilityGrid entries={catalog.entries} />
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">多租户 / 角色 / 助理</h2>
        <TenancyPanel tenants={tenants} roles={roles} assistants={assistants} onChanged={refresh} />
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">A2A（助理对助理）</h2>
        <A2APanel assistants={assistants} />
      </section>
    </div>
  )
}
