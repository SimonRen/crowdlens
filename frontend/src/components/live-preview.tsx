import { useEffect, useRef, useState } from 'react'
import { useMonitorStore } from '../stores/monitor'

export function LivePreview() {
  const imgRef = useRef<HTMLImageElement>(null)
  const { sessionId, isConnected, stats } = useMonitorStore()
  const [stale, setStale] = useState(false)
  const [streamKey, setStreamKey] = useState(0)
  const lastFrameTime = useRef(Date.now())

  // Set initial stream key when session starts
  useEffect(() => {
    if (sessionId) {
      setStreamKey(Date.now())
      setStale(false)
    }
  }, [sessionId])

  // Use SSE stats as heartbeat proxy for stream liveness.
  // MJPEG onLoad only fires on the first frame of a multipart response,
  // so we track the SSE stats timestamp instead (arrives at similar frequency).
  useEffect(() => {
    if (stats?.timestamp) {
      lastFrameTime.current = Date.now()
      setStale(false)
    }
  }, [stats?.timestamp])

  // Reconnect logic: re-set src if no SSE stats for 3s (proxy for stale stream)
  useEffect(() => {
    if (!sessionId) return
    const interval = setInterval(() => {
      if (Date.now() - lastFrameTime.current > 3000) {
        setStale(true)
        setStreamKey(Date.now())
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [sessionId])

  return (
    <div className="relative bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg overflow-hidden aspect-video">
      {sessionId ? (
        <>
          <img
            ref={imgRef}
            src={`/api/stream?t=${streamKey}`}
            alt="Live feed"
            className="w-full h-full object-contain"
          />
          {stale && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/60">
              <span className="text-[var(--color-muted)] font-[family-name:var(--font-body)]">
                Reconnecting...
              </span>
            </div>
          )}
          {/* Connection status dot */}
          <div className="absolute top-3 left-3 flex items-center gap-2">
            <div
              className={`w-2.5 h-2.5 rounded-full ${
                isConnected ? 'bg-[var(--color-accent)] shadow-[0_0_8px_var(--color-accent)]' : 'bg-red-500'
              }`}
            />
            <span className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)]">
              {isConnected ? 'Live' : 'Disconnected'}
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
        <div className="w-full h-full flex items-center justify-center min-h-[300px]">
          <span className="text-[var(--color-muted)] font-[family-name:var(--font-body)]">
            Select a channel and start monitoring
          </span>
        </div>
      )}
    </div>
  )
}
