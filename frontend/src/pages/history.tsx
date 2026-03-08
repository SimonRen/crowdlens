import { useState } from 'react'
import { SessionTable } from '../components/session-table'
import { SessionDetail } from '../components/session-detail'
import type { SessionStats } from '../lib/api'

export function History() {
  const [selectedSession, setSelectedSession] = useState<SessionStats | null>(null)

  return (
    <div className="max-w-[1200px] mx-auto p-4">
      <h1 className="text-2xl font-bold text-[var(--color-text)] font-[family-name:var(--font-heading)] mb-6">
        Session History
      </h1>

      {selectedSession ? (
        <SessionDetail stats={selectedSession} onBack={() => setSelectedSession(null)} />
      ) : (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg">
          <SessionTable onSelectSession={setSelectedSession} />
        </div>
      )}
    </div>
  )
}
