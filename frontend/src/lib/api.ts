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
export const resetSystem = () =>
  api.post('reset').json<{ status: string; stopped_sessions: number }>()

export interface MatchEvent {
  type: 'match'
  track_id: number
  similarity: number
  frame_jpeg: string
  crop_jpeg: string
  timestamp: string
}

export interface TargetStatus {
  active: boolean
  threshold: number
  thumbnail_url: string | null
}

export const uploadTarget = (file: File, threshold: number) => {
  const form = new FormData()
  form.append('file', file)
  form.append('threshold', String(threshold))
  return api.post('target/upload', { body: form }).json<{ status: string; threshold: number; has_face: boolean }>()
}

export const getTargetStatus = () =>
  api.get('target').json<TargetStatus>()

export const clearTarget = () =>
  api.post('target/clear').json<{ status: string }>()

export const resumeAfterMatch = () =>
  api.post('target/resume').json<{ status: string }>()

export const updateThreshold = (threshold: number) =>
  api.post('target/threshold', { json: { threshold } }).json<{ status: string; threshold: number }>()
