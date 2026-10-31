import type { CapabilityTag } from '../types'

/** 对话界面/Dashboard 里挂在一条能力上的"颜色 chip"——按名词类别上色，
 * 写动词再叠一个红色小点，一眼能看出"这条消息做了什么、会不会改数据"。 */
export function CapabilityChip({ tag }: { tag: CapabilityTag }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium"
      style={{
        backgroundColor: tag.color.bg,
        color: tag.color.fg,
        borderColor: tag.color.border,
      }}
      title={`${tag.category_label} · ${tag.kind === 'write' ? '写操作' : '只读'}`}
    >
      {tag.destructive && <span className="h-1.5 w-1.5 rounded-full bg-red-600" />}
      <span className="font-semibold">{tag.verb_zh}</span>
      <span>·</span>
      <span>{tag.noun_zh}</span>
      <span className="opacity-60">({tag.noun})</span>
    </span>
  )
}
