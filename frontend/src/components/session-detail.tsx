import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import dayjs from 'dayjs'
import type { SessionStats } from '../lib/api'

const AREAS = [
  { key: 'men_in_frame', name: 'Men', color: '#3B82F6' },
  { key: 'women_in_frame', name: 'Women', color: '#EC4899' },
  { key: 'children_in_frame', name: 'Children', color: '#22C55E' },
  { key: 'unknown_in_frame', name: 'Unknown', color: '#6B7280' },
]

const STAT_ITEMS = [
  { key: 'men', label: 'Men', color: '#3B82F6' },
  { key: 'women', label: 'Women', color: '#EC4899' },
  { key: 'children', label: 'Children', color: '#22C55E' },
  { key: 'unknown', label: 'Unknown', color: '#6B7280' },
] as const

interface Props {
  stats: SessionStats
  onBack: () => void
}

export function SessionDetail({ stats, onBack }: Props) {
  const chartData = stats.snapshots.map((s) => ({
    ...s,
    time: dayjs(s.timestamp).format('HH:mm:ss'),
  }))

  return (
    <div className="space-y-4">
      <button
        onClick={onBack}
        className="text-sm text-[var(--color-accent)] hover:text-[var(--color-accent)]/80 cursor-pointer transition-colors duration-200 font-[family-name:var(--font-body)]"
      >
        &larr; Back to sessions
      </button>

      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-4">
        <h3 className="text-xs uppercase tracking-wider text-[var(--color-muted)] font-[family-name:var(--font-heading)] mb-1">
          Session Summary
        </h3>
        <p className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)] mb-4">
          Channel: {stats.channel_id} &bull; Started: {dayjs(stats.started_at).format('MMM D, HH:mm:ss')}
          {stats.stopped_at && ` — Stopped: ${dayjs(stats.stopped_at).format('HH:mm:ss')}`}
        </p>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {STAT_ITEMS.map((item) => (
            <div key={item.key} className="bg-[var(--color-bg)] rounded-lg p-3 text-center">
              <div className="flex items-center justify-center gap-1.5 mb-1">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                <span className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)]">
                  {item.label}
                </span>
              </div>
              <span className="text-xl font-bold text-[var(--color-text)] font-[family-name:var(--font-heading)] tabular-nums">
                {stats.summary[item.key]}
              </span>
            </div>
          ))}
        </div>
      </div>

      {chartData.length > 0 && (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-4">
          <h3 className="text-xs uppercase tracking-wider text-[var(--color-muted)] font-[family-name:var(--font-heading)] mb-4">
            People Over Time
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
              <XAxis dataKey="time" stroke="#94A3B8" tick={{ fontSize: 11, fill: '#94A3B8' }} />
              <YAxis stroke="#94A3B8" tick={{ fontSize: 11, fill: '#94A3B8' }} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0F172A',
                  border: '1px solid #1E293B',
                  borderRadius: '8px',
                  color: '#F8FAFC',
                  fontSize: '12px',
                }}
              />
              {AREAS.map((area) => (
                <Area
                  key={area.key}
                  type="monotone"
                  dataKey={area.key}
                  name={area.name}
                  stackId="1"
                  stroke={area.color}
                  fill={area.color}
                  fillOpacity={0.2}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
