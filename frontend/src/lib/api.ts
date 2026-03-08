import ky from 'ky'

const api = ky.create({ prefixUrl: '/api' })

export interface Channel {
  id: string
  filename: string
  label: string
}

export interface Session {
  id: string
  channel_id: string
  started_at: string
  stopped_at: string | null
  status: 'active' | 'stopped'
}

export interface StatsEvent {
  in_frame: { men: number; women: number; children: number; unknown: number }
  session_total: { men: number; women: number; children: number; unknown: number }
  fps: number
  session_id: string
  timestamp: string
}

export interface SessionStats extends Session {
  summary: { men: number; women: number; children: number; unknown: number; total: number }
  snapshots: Array<{
    timestamp: string
    men_in_frame: number
    women_in_frame: number
    children_in_frame: number
    unknown_in_frame: number
  }>
}

export const fetchChannels = () => api.get('channels').json<Channel[]>()
export const fetchSessions = () => api.get('sessions').json<Session[]>()
export const fetchSessionStats = (id: string) => api.get(`sessions/${id}/stats`).json<SessionStats>()
export const startSession = (channel_id: string) =>
  api.post('sessions/start', { json: { channel_id } }).json<{ session_id: string }>()
export const stopSession = (session_id: string) =>
  api.post('sessions/stop', { json: { session_id } }).json<{ session_id: string }>()
