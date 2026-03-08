import { useEffect, useState } from 'react'
import { fetchChannels, type Channel } from '../lib/api'

interface Props {
  value: string
  onChange: (id: string) => void
}

export function ChannelSelector({ value, onChange }: Props) {
  const [channels, setChannels] = useState<Channel[]>([])

  useEffect(() => {
    fetchChannels().then(setChannels).catch(console.error)
  }, [])

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-[var(--color-surface)] text-[var(--color-text)] border border-[var(--color-border)] rounded-lg px-4 py-2 font-[family-name:var(--font-body)] text-sm focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/20 cursor-pointer transition-colors duration-200"
    >
      <option value="">Select a channel...</option>
      {channels.map((ch) => (
        <option key={ch.id} value={ch.id}>
          {ch.label}
        </option>
      ))}
    </select>
  )
}
