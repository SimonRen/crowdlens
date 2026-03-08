import { useMonitorStore } from '../stores/monitor'

const CLASSIFICATIONS = [
  { key: 'men', label: 'Men', color: 'var(--color-man)' },
  { key: 'women', label: 'Women', color: 'var(--color-woman)' },
  { key: 'children', label: 'Children', color: 'var(--color-child)' },
  { key: 'unknown', label: 'Unknown', color: 'var(--color-unknown)' },
] as const

function StatRow({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <div className="flex items-center gap-2">
        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
        <span className="text-sm text-[var(--color-muted)] font-[family-name:var(--font-body)]">
          {label}
        </span>
      </div>
      <span className="text-sm font-semibold text-[var(--color-text)] font-[family-name:var(--font-heading)] tabular-nums">
        {value}
      </span>
    </div>
  )
}

export function StatsPanel() {
  const { stats } = useMonitorStore()

  const inFrame = stats?.in_frame ?? { men: 0, women: 0, children: 0, unknown: 0 }
  const sessionTotal = stats?.session_total ?? { men: 0, women: 0, children: 0, unknown: 0 }

  return (
    <div className="flex flex-col gap-4">
      {/* In Frame Now */}
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-4">
        <h3 className="text-xs uppercase tracking-wider text-[var(--color-muted)] font-[family-name:var(--font-heading)] mb-3">
          In Frame Now
        </h3>
        <div className="text-3xl font-bold text-[var(--color-text)] font-[family-name:var(--font-heading)] mb-3 tabular-nums">
          {inFrame.men + inFrame.women + inFrame.children + inFrame.unknown}
        </div>
        {CLASSIFICATIONS.map((c) => (
          <StatRow
            key={c.key}
            label={c.label}
            value={inFrame[c.key]}
            color={c.color}
          />
        ))}
      </div>

      {/* Session Total */}
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-4">
        <h3 className="text-xs uppercase tracking-wider text-[var(--color-muted)] font-[family-name:var(--font-heading)] mb-3">
          Session Total (Unique)
        </h3>
        <div className="text-3xl font-bold text-[var(--color-text)] font-[family-name:var(--font-heading)] mb-3 tabular-nums">
          {sessionTotal.men + sessionTotal.women + sessionTotal.children + sessionTotal.unknown}
        </div>
        {CLASSIFICATIONS.map((c) => (
          <StatRow
            key={c.key}
            label={c.label}
            value={sessionTotal[c.key]}
            color={c.color}
          />
        ))}
      </div>
    </div>
  )
}
