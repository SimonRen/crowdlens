import { useState } from 'react'
import { useMonitorStore } from '../stores/monitor'
import { resumeAfterMatch } from '../lib/api'

export function MatchOverlay() {
  const { matchResult, targetThumbnailUrl, setMatchResult } = useMonitorStore()
  const [resuming, setResuming] = useState(false)

  if (!matchResult) return null

  const handleResume = async () => {
    setResuming(true)
    try {
      await resumeAfterMatch()
      setMatchResult(null)
    } catch (err) {
      console.error(err)
    } finally {
      setResuming(false)
    }
  }

  const similarity = (matchResult.similarity * 100).toFixed(1)

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm rounded-lg">
      <div className="flex flex-col items-center gap-6 p-8 max-w-md">
        {/* Title */}
        <div className="bg-red-500/20 border border-red-500/50 rounded-lg px-6 py-2">
          <h2 className="text-lg font-bold text-red-400 font-[family-name:var(--font-heading)] tracking-wider">
            MATCH FOUND
          </h2>
        </div>

        {/* Photo comparison */}
        <div className="flex items-center gap-4">
          {/* Target photo */}
          <div className="flex flex-col items-center gap-1">
            <img
              src={targetThumbnailUrl || ''}
              alt="Target"
              className="w-24 h-24 rounded-lg object-cover border-2 border-[var(--color-border)]"
            />
            <span className="text-[10px] text-[var(--color-muted)] font-[family-name:var(--font-body)]">
              Target
            </span>
          </div>

          {/* Similarity */}
          <div className="flex flex-col items-center gap-1">
            <span className="text-2xl font-bold text-[var(--color-accent)] font-[family-name:var(--font-heading)]">
              {similarity}%
            </span>
            <span className="text-[10px] text-[var(--color-muted)] font-[family-name:var(--font-body)]">
              match
            </span>
          </div>

          {/* Matched crop */}
          <div className="flex flex-col items-center gap-1">
            <img
              src={`data:image/jpeg;base64,${matchResult.crop_jpeg}`}
              alt="Matched person"
              className="w-24 h-24 rounded-lg object-cover border-2 border-red-500/50"
            />
            <span className="text-[10px] text-[var(--color-muted)] font-[family-name:var(--font-body)]">
              Detected
            </span>
          </div>
        </div>

        {/* Details */}
        <p className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)]">
          Track #{matchResult.track_id} &middot; {new Date(matchResult.timestamp).toLocaleString()}
        </p>

        {/* Resume button */}
        <button
          onClick={handleResume}
          disabled={resuming}
          className="bg-[var(--color-accent)] hover:bg-[var(--color-accent)]/90 text-[var(--color-bg)] px-8 py-3 rounded-lg font-semibold font-[family-name:var(--font-body)] cursor-pointer transition-colors duration-200 disabled:opacity-50"
        >
          {resuming ? 'Resuming...' : 'Resume Monitoring'}
        </button>
      </div>
    </div>
  )
}
