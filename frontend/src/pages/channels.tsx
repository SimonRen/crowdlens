import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { fetchChannels, resetSystem, type Channel } from '../lib/api'

export function Channels() {
  const [channels, setChannels] = useState<Channel[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchChannels()
      .then(setChannels)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <nav className="bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3 flex items-center justify-between">
        <h1 className="text-lg font-bold font-[family-name:var(--font-heading)] text-[var(--color-accent)]">
          CrowdLens
        </h1>
        <button
          onClick={() => resetSystem().catch(console.error)}
          className="border border-[var(--color-border)] hover:bg-[var(--color-surface)] text-[var(--color-muted)] hover:text-[var(--color-text)] px-4 py-2 rounded-lg font-semibold font-[family-name:var(--font-body)] cursor-pointer transition-colors duration-200 text-sm"
        >
          Reset
        </button>
      </nav>

      <div className="p-8 max-w-4xl mx-auto">
        <h2 className="text-xl font-bold font-[family-name:var(--font-heading)] text-[var(--color-text)] mb-6">
          Select a Channel
        </h2>

        {loading ? (
          <p className="text-sm text-[var(--color-muted)] font-[family-name:var(--font-body)]">
            Loading channels...
          </p>
        ) : channels.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)] font-[family-name:var(--font-body)]">
            No channels found. Add video files to the videos directory.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {channels.map((ch) => (
              <Link
                key={ch.id}
                to="/$channelId"
                params={{ channelId: ch.id }}
                className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-6 hover:border-[var(--color-accent)] transition-colors duration-200 group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center">
                    <span className="text-[var(--color-accent)] font-[family-name:var(--font-heading)] font-bold text-sm">
                      {ch.label.charAt(0)}
                    </span>
                  </div>
                  <div>
                    <p className="font-semibold text-[var(--color-text)] font-[family-name:var(--font-heading)] group-hover:text-[var(--color-accent)] transition-colors">
                      {ch.label}
                    </p>
                    <p className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)]">
                      {ch.filename}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </>
  )
}
