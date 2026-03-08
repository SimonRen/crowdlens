import { create } from 'zustand'
import type { StatsEvent } from '../lib/api'

interface MonitorState {
  sessionId: string | null
  stats: StatsEvent | null
  chartData: Array<StatsEvent & { time: string }>
  isConnected: boolean
  setSessionId: (id: string | null) => void
  setStats: (stats: StatsEvent) => void
  setConnected: (connected: boolean) => void
  clearChart: () => void
}

export const useMonitorStore = create<MonitorState>((set) => ({
  sessionId: null,
  stats: null,
  chartData: [],
  isConnected: false,
  setSessionId: (id) => set({ sessionId: id }),
  setStats: (stats) =>
    set((state) => ({
      stats,
      chartData: [
        ...state.chartData.slice(-60),
        { ...stats, time: new Date(stats.timestamp).toLocaleTimeString() },
      ],
    })),
  setConnected: (connected) => set({ isConnected: connected }),
  clearChart: () => set({ chartData: [], stats: null }),
}))
