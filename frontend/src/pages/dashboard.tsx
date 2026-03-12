import { useState } from 'react'
import { Link, useParams } from '@tanstack/react-router'
import { LivePreview } from '../components/live-preview'
import { StatsPanel } from '../components/stats-panel'
import { TimeChart } from '../components/time-chart'
import { TargetSearchPanel } from '../components/target-search'
import { MatchOverlay } from '../components/match-overlay'
import { useSSE } from '../hooks/use-sse'
import { useMonitorStore } from '../stores/monitor'
import { startSession, stopSession, resetSystem } from '../lib/api'

export function Dashboard() {
  const { channelId } = useParams({ from: '/$channelId' })
  const { sessionId, setSessionId, clearSession } = useMonitorStore()
  const [loading, setLoading] = useState(false)

  useSSE()

  const handleStop = async () => {
    if (!sessionId) return
    setLoading(true)
    try {
      await stopSession(sessionId)
      setSessionId(null)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleStart = async () => {
    setLoading(true)
    try {
      clearSession()
      const res = await startSession(channelId)
      setSessionId(res.session_id)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async () => {
    setLoading(true)
    try {
      await resetSystem()
      setSessionId(null)
      clearSession()
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {/* Nav bar with back link */}
      <nav className="bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3 flex items-center gap-4">
        <Link
          to="/"
          className="text-lg font-bold font-[family-name:var(--font-heading)] text-[var(--color-accent)] hover:opacity-80 transition-opacity"
        >
          CrowdLens
        </Link>
        <span className="text-sm text-[var(--color-muted)] font-[family-name:var(--font-body)]">
          / {channelId.replace('-', ' ').replace('_', ' ')}
        </span>
      </nav>

      <div className="flex flex-col p-4 min-h-[calc(100vh-49px)] gap-4">
        {/* Top bar */}
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg px-4 py-3 flex items-center justify-end gap-2">
          {sessionId ? (
            <button
              onClick={handleStop}
              disabled={loading}
              className="bg-red-500 hover:bg-red-600 text-white px-6 py-2 rounded-lg font-semibold font-[family-name:var(--font-body)] cursor-pointer transition-colors duration-200 disabled:opacity-50"
            >
              {loading ? 'Stopping...' : 'Stop'}
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={loading}
              className="bg-[var(--color-accent)] hover:bg-[var(--color-accent)]/90 text-[var(--color-bg)] px-6 py-2 rounded-lg font-semibold font-[family-name:var(--font-body)] cursor-pointer transition-colors duration-200 disabled:opacity-50"
            >
              {loading ? 'Starting...' : 'Start Monitoring'}
            </button>
          )}
          <button
            onClick={handleReset}
            disabled={loading}
            className="border border-[var(--color-border)] hover:bg-[var(--color-surface)] text-[var(--color-muted)] hover:text-[var(--color-text)] px-4 py-2 rounded-lg font-semibold font-[family-name:var(--font-body)] cursor-pointer transition-colors duration-200 disabled:opacity-50"
          >
            Reset
          </button>
        </div>

        {/* Main area: video left, stats + chart right */}
        <div className="flex flex-col lg:flex-row gap-4 flex-1">
          <div className="lg:w-2/3 flex relative">
            <LivePreview />
            <MatchOverlay />
          </div>
          <div className="lg:w-1/3 flex flex-col gap-4">
            <TargetSearchPanel />
            <StatsPanel />
            <TimeChart />
          </div>
        </div>

        {/* Footer */}
        <footer className="text-center py-3 text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)] border-t border-[var(--color-border)]">
          &copy; 2026, Target Group &middot; Build: {__BUILD_TIME__}
        </footer>
      </div>
    </>
  )
}
