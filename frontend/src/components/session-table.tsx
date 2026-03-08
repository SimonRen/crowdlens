import { useEffect, useState } from 'react'
import dayjs from 'dayjs'
import { fetchSessions, fetchSessionStats, type Session, type SessionStats } from '../lib/api'

function formatDuration(start: string, end: string | null): string {
  if (!end) return 'Running...'
  const seconds = dayjs(end).diff(dayjs(start), 'second')
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

interface Props {
  onSelectSession: (stats: SessionStats) => void
}

export function SessionTable({ onSelectSession }: Props) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchSessions()
      .then(setSessions)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleView = async (session: Session) => {
    try {
      const stats = await fetchSessionStats(session.id)
      onSelectSession(stats)
    } catch (err) {
      console.error(err)
    }
  }

  if (loading) {
    return (
      <div className="text-center py-12 text-[var(--color-muted)] font-[family-name:var(--font-body)]">
        Loading sessions...
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="text-center py-12 text-[var(--color-muted)] font-[family-name:var(--font-body)]">
        No sessions yet. Start monitoring from the Dashboard.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[var(--color-border)]">
            {['Channel', 'Started', 'Duration', 'Status', 'Actions'].map((h) => (
              <th
                key={h}
                className="text-left text-xs uppercase tracking-wider text-[var(--color-muted)] font-[family-name:var(--font-heading)] py-3 px-4"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => (
            <tr
              key={session.id}
              className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface-hover)] transition-colors duration-150"
            >
              <td className="py-3 px-4 text-sm text-[var(--color-text)] font-[family-name:var(--font-body)]">
                {session.channel_id}
              </td>
              <td className="py-3 px-4 text-sm text-[var(--color-muted)] font-[family-name:var(--font-body)]">
                {dayjs(session.started_at).format('MMM D, HH:mm:ss')}
              </td>
              <td className="py-3 px-4 text-sm text-[var(--color-muted)] font-[family-name:var(--font-heading)] tabular-nums">
                {formatDuration(session.started_at, session.stopped_at)}
              </td>
              <td className="py-3 px-4">
                <span
                  className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full ${
                    session.status === 'active'
                      ? 'text-[var(--color-accent)] bg-[var(--color-accent)]/10'
                      : 'text-[var(--color-unknown)] bg-[var(--color-unknown)]/10'
                  }`}
                >
                  <div
                    className={`w-1.5 h-1.5 rounded-full ${
                      session.status === 'active' ? 'bg-[var(--color-accent)]' : 'bg-[var(--color-unknown)]'
                    }`}
                  />
                  {session.status === 'active' ? 'Active' : 'Stopped'}
                </span>
              </td>
              <td className="py-3 px-4">
                <button
                  onClick={() => handleView(session)}
                  className="text-sm text-[var(--color-accent)] hover:text-[var(--color-accent)]/80 cursor-pointer transition-colors duration-200 font-[family-name:var(--font-body)]"
                >
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
