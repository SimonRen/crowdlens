import { create } from 'zustand'
import type { StatsEvent, MatchEvent } from '../lib/api'

interface MonitorState {
  sessionId: string | null
  stats: StatsEvent | null
  chartData: Array<StatsEvent & { time: string }>
  isConnected: boolean
  targetActive: boolean
  targetThreshold: number
  targetThumbnailUrl: string | null
  matchResult: MatchEvent | null
  setSessionId: (id: string | null) => void
  setStats: (stats: StatsEvent) => void
  setConnected: (connected: boolean) => void
  clearSession: () => void
  setTargetActive: (active: boolean, threshold?: number, thumbnailUrl?: string | null) => void
  setTargetThreshold: (threshold: number) => void
  setMatchResult: (result: MatchEvent | null) => void
  clearTarget: () => void
}

export const useMonitorStore = create<MonitorState>((set) => ({
  sessionId: null,
  stats: null,
  chartData: [],
  isConnected: false,
  targetActive: false,
  targetThreshold: 0.5,
  targetThumbnailUrl: null,
  matchResult: null,
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
  clearSession: () => set({ chartData: [], stats: null, matchResult: null }),
  setTargetActive: (active, threshold, thumbnailUrl) =>
    set((state) => ({
      targetActive: active,
      targetThreshold: threshold ?? state.targetThreshold,
      targetThumbnailUrl: thumbnailUrl !== undefined ? thumbnailUrl : state.targetThumbnailUrl,
    })),
  setTargetThreshold: (threshold) => set({ targetThreshold: threshold }),
  setMatchResult: (result) => set({ matchResult: result }),
  clearTarget: () =>
    set({ targetActive: false }),
}))
