import ky from 'ky'

const api = ky.create({ prefixUrl: '/api' })

export interface Channel {
  id: string
  filename: string
  label: string
}

export interface StatsEvent {
  in_frame: { men: number; women: number; children: number; unknown: number }
  session_total: { men: number; women: number; children: number; unknown: number }
  fps: number
  session_id: string
  timestamp: string
}

export const fetchChannels = () => api.get('channels').json<Channel[]>()
export const startSession = (channel_id: string) =>
  api.post('sessions/start', { json: { channel_id } }).json<{ session_id: string }>()
export const stopSession = (session_id: string) =>
  api.post('sessions/stop', { json: { session_id } }).json<{ session_id: string }>()
