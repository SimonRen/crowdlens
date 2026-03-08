import { useMonitorStore } from '../stores/monitor'

const CLASSIFICATIONS = [
  { key: 'men', label: 'Men', color: 'var(--color-man)', bg: 'var(--color-man)' },
  { key: 'women', label: 'Women', color: 'var(--color-woman)', bg: 'var(--color-woman)' },
  { key: 'children', label: 'Children', color: 'var(--color-child)', bg: 'var(--color-child)' },
  { key: 'unknown', label: 'Unknown', color: 'var(--color-unknown)', bg: 'var(--color-unknown)' },
] as const

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-4">
      <h3 className="text-xs uppercase tracking-wider text-[var(--color-muted)] font-[family-name:var(--font-heading)] mb-3">
        {title}
      </h3>
      {children}
    </div>
  )
}


function ClassificationCards({ data }: { data: { men: number; women: number; children: number; unknown: number } }) {
  const total = data.men + data.women + data.children + data.unknown
  return (
    <div className="grid grid-cols-5 gap-2">
      {/* Total card */}
      <div
        className="rounded-lg p-3 text-center"
        style={{ backgroundColor: 'color-mix(in srgb, var(--color-text) 8%, transparent)', borderLeft: '3px solid var(--color-text)' }}
      >
        <div className="text-3xl font-bold font-[family-name:var(--font-heading)] tabular-nums text-[var(--color-text)]">
          {total}
        </div>
        <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)] font-[family-name:var(--font-heading)] mt-1">
          Total
        </div>
      </div>
      {CLASSIFICATIONS.map((c) => (
        <div
          key={c.key}
          className="rounded-lg p-3 text-center"
          style={{ backgroundColor: `color-mix(in srgb, ${c.bg} 15%, transparent)`, borderLeft: `3px solid ${c.color}` }}
        >
          <div
            className="text-3xl font-bold font-[family-name:var(--font-heading)] tabular-nums"
            style={{ color: c.color }}
          >
            {data[c.key]}
          </div>
          <div className="text-[10px] uppercase tracking-wider text-[var(--color-muted)] font-[family-name:var(--font-heading)] mt-1">
            {c.label}
          </div>
        </div>
      ))}
    </div>
  )
}

export function StatsPanel() {
  const { stats } = useMonitorStore()

  const inFrame = stats?.in_frame ?? { men: 0, women: 0, children: 0, unknown: 0 }
  const sessionTotal = stats?.session_total ?? { men: 0, women: 0, children: 0, unknown: 0 }
  const fps = stats?.fps ?? 0

  return (
    <div className="flex flex-col gap-4">
      {/* Pipeline Info */}
      <Card title="Pipeline">
        <div className="flex items-baseline gap-2 mb-2">
          <span className="text-3xl font-bold text-[var(--color-accent)] font-[family-name:var(--font-heading)] tabular-nums">
            {fps}
          </span>
          <span className="text-sm text-[var(--color-muted)] font-[family-name:var(--font-body)]">
            FPS
          </span>
        </div>
      </Card>

      {/* In Frame Now */}
      <Card title="In Frame Now">
        <ClassificationCards data={inFrame} />
      </Card>

      {/* Session Total */}
      <Card title="Session Total (Unique)">
        <ClassificationCards data={sessionTotal} />
      </Card>
    </div>
  )
}
