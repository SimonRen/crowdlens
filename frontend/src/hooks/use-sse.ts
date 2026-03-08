import { useEffect, useRef } from 'react'
import { useMonitorStore } from '../stores/monitor'
import type { StatsEvent } from '../lib/api'

export function useSSE() {
  const { setStats, setConnected } = useMonitorStore()
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    const es = new EventSource('/api/events')
    eventSourceRef.current = es

    es.addEventListener('stats', (e) => {
      const data: StatsEvent = JSON.parse(e.data)
      setStats(data)
      setConnected(true)
    })

    es.onerror = () => {
      setConnected(false)
    }

    es.onopen = () => {
      setConnected(true)
    }

    return () => {
      es.close()
      eventSourceRef.current = null
    }
  }, [setStats, setConnected])
}
