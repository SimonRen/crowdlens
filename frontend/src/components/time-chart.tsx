import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useMonitorStore } from '../stores/monitor'

const AREAS = [
  { key: 'men', name: 'Men', color: '#3B82F6' },
  { key: 'women', name: 'Women', color: '#EC4899' },
  { key: 'children', name: 'Children', color: '#22C55E' },
  { key: 'unknown', name: 'Unknown', color: '#6B7280' },
]

export function TimeChart() {
  const { chartData } = useMonitorStore()

  const data = chartData
    .filter((d) => d.in_frame != null)
    .map((d) => ({
      time: d.time,
      men: d.in_frame.men,
      women: d.in_frame.women,
      children: d.in_frame.children,
      unknown: d.in_frame.unknown,
    }))

  return (
    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-4">
      <h3 className="text-xs uppercase tracking-wider text-[var(--color-muted)] font-[family-name:var(--font-heading)] mb-4">
        People Over Time
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
          <XAxis
            dataKey="time"
            stroke="#94A3B8"
            tick={{ fontSize: 11, fill: '#94A3B8' }}
          />
          <YAxis
            stroke="#94A3B8"
            tick={{ fontSize: 11, fill: '#94A3B8' }}
            allowDecimals={false}
          />
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
  )
}
