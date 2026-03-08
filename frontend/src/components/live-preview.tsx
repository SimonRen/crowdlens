import { useEffect, useState } from 'react'
import { useMonitorStore } from '../stores/monitor'

export function LivePreview() {
  const { sessionId, isConnected, stats } = useMonitorStore()
  const [streamKey, setStreamKey] = useState(0)

  // New stream connection when session starts
  useEffect(() => {
    if (sessionId) {
      setStreamKey(Date.now())
    }
  }, [sessionId])

  return (
    <div className="relative bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg overflow-hidden w-full h-full flex items-center justify-center min-h-[300px]">
      {sessionId ? (
        <>
          <img
            src={`/api/stream?t=${streamKey}`}
            alt="Live feed"
            className="max-w-full max-h-full object-contain"
          />
          {/* Connection status dot */}
          <div className="absolute top-3 left-3 flex items-center gap-2">
            <div
              className={`w-2.5 h-2.5 rounded-full ${
                isConnected ? 'bg-[var(--color-accent)] shadow-[0_0_8px_var(--color-accent)]' : 'bg-red-500'
              }`}
            />
            <span className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)]">
              {isConnected ? 'Live' : 'Connecting...'}
            </span>
          </div>
          {/* FPS counter */}
          {stats && (
            <div className="absolute top-3 right-3">
              <span className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-heading)] bg-black/50 px-2 py-1 rounded">
                {stats.fps} FPS
              </span>
            </div>
          )}
        </>
      ) : (
        <span className="text-[var(--color-muted)] font-[family-name:var(--font-body)]">
          Select a channel and start monitoring
        </span>
      )}
    </div>
  )
}
