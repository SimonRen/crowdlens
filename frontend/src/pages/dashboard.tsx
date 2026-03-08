import { useState } from 'react'
import { ChannelSelector } from '../components/channel-selector'
import { LivePreview } from '../components/live-preview'
import { StatsPanel } from '../components/stats-panel'
import { TimeChart } from '../components/time-chart'
import { useSSE } from '../hooks/use-sse'
import { useMonitorStore } from '../stores/monitor'
import { startSession, stopSession } from '../lib/api'

export function Dashboard() {
  const [channelId, setChannelId] = useState('')
  const { sessionId, setSessionId, clearChart } = useMonitorStore()
  const [loading, setLoading] = useState(false)

  useSSE()

  const handleStart = async () => {
    if (!channelId) return
    setLoading(true)
    try {
      clearChart()
      const res = await startSession(channelId)
      setSessionId(res.session_id)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

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

  return (
    <div className="flex flex-col gap-4 p-4 min-h-screen">
      {/* Top bar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <ChannelSelector value={channelId} onChange={setChannelId} />
        </div>
        <div>
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
              disabled={loading || !channelId}
              className="bg-[var(--color-accent)] hover:bg-[var(--color-accent)]/90 text-[var(--color-bg)] px-6 py-2 rounded-lg font-semibold font-[family-name:var(--font-body)] cursor-pointer transition-colors duration-200 disabled:opacity-50"
            >
              {loading ? 'Starting...' : 'Start Monitoring'}
            </button>
          )}
        </div>
      </div>

      {/* Main area */}
      <div className="flex flex-col lg:flex-row gap-4 flex-1">
        <div className="lg:w-2/3">
          <LivePreview />
        </div>
        <div className="lg:w-1/3">
          <StatsPanel />
        </div>
      </div>

      {/* Chart */}
      <TimeChart />
    </div>
  )
}
