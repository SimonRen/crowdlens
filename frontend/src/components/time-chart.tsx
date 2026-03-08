import { useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useMonitorStore } from '../stores/monitor'

const METRICS = [
  { key: 'total', label: 'Total', color: 'var(--color-text)' },
  { key: 'men', label: 'Men', color: 'var(--color-man)' },
  { key: 'women', label: 'Women', color: 'var(--color-woman)' },
  { key: 'children', label: 'Children', color: 'var(--color-child)' },
  { key: 'unknown', label: 'Unknown', color: 'var(--color-unknown)' },
] as const

type MetricKey = (typeof METRICS)[number]['key']

export function TimeChart() {
  const { chartData } = useMonitorStore()
  const [selected, setSelected] = useState<Set<MetricKey>>(new Set(['total']))

  const toggle = (key: MetricKey) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        if (next.size > 1) next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const data = chartData
    .filter((d) => d.in_frame != null)
    .map((d) => ({
      time: d.time,
      total: d.in_frame.men + d.in_frame.women + d.in_frame.children + d.in_frame.unknown,
      men: d.in_frame.men,
      women: d.in_frame.women,
      children: d.in_frame.children,
      unknown: d.in_frame.unknown,
    }))

  return (
    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs uppercase tracking-wider text-[var(--color-muted)] font-[family-name:var(--font-heading)]">
          People Over Time
        </h3>
        <div className="flex gap-1.5 flex-wrap">
          {METRICS.map((m) => (
            <button
              key={m.key}
              onClick={() => toggle(m.key)}
              className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider font-[family-name:var(--font-heading)] cursor-pointer transition-colors duration-150"
              style={{
                backgroundColor: selected.has(m.key)
                  ? `color-mix(in srgb, ${m.color} 20%, transparent)`
                  : 'transparent',
                color: selected.has(m.key) ? m.color : 'var(--color-muted)',
                border: `1px solid ${selected.has(m.key) ? m.color : 'var(--color-border)'}`,
              }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="time"
            stroke="var(--color-muted)"
            tick={{ fontSize: 11, fill: 'var(--color-muted)' }}
          />
          <YAxis
            stroke="var(--color-muted)"
            tick={{ fontSize: 11, fill: 'var(--color-muted)' }}
            allowDecimals={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '8px',
              color: 'var(--color-text)',
              fontSize: '12px',
            }}
          />
          {METRICS.map((m) =>
            selected.has(m.key) ? (
              <Line
                key={m.key}
                type="monotone"
                dataKey={m.key}
                name={m.label}
                stroke={m.color}
                strokeWidth={m.key === 'total' ? 2 : 1.5}
                dot={false}
                activeDot={{ r: 3 }}
              />
            ) : null,
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
