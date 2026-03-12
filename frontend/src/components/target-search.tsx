import { useCallback, useRef, useState } from 'react'
import { useMonitorStore } from '../stores/monitor'
import { uploadTarget, clearTarget, updateThreshold } from '../lib/api'

export function TargetSearchPanel() {
  const { targetActive, targetThreshold, targetThumbnailUrl, matchResult, setTargetActive, setTargetThreshold, setMatchResult, clearTarget: clearTargetStore } = useMonitorStore()
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(null)

  const handleUpload = useCallback(async (file: File) => {
    setUploading(true)
    setError(null)
    setMatchResult(null) // clear previous match when uploading new target
    try {
      const res = await uploadTarget(file, targetThreshold)
      setTargetActive(true, res.threshold, '/api/target/thumbnail?t=' + Date.now())
    } catch (err: any) {
      const msg = await err?.response?.json?.().catch(() => null)
      setError(msg?.detail || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }, [targetThreshold, setTargetActive, setMatchResult])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    e.target.value = '' // reset for re-upload
  }

  const handleClear = async () => {
    try {
      await clearTarget()
      clearTargetStore()
    } catch (err) {
      console.error(err)
    }
  }

  const handleThresholdChange = (value: number) => {
    setTargetThreshold(value)
    // Only send API call when target is active
    if (!targetActive) return
    // Debounce the API call
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      updateThreshold(value).catch(console.error)
    }, 300)
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('image/')) {
      handleUpload(file)
    }
  }, [handleUpload])

  return (
    <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-4">
      <h3 className="text-sm font-semibold text-[var(--color-text)] font-[family-name:var(--font-heading)] mb-3">
        Target Search
      </h3>

      {/* State 1: Active target — searching or matched */}
      {targetActive && targetThumbnailUrl ? (
        <div className="flex items-start gap-3 mb-3">
          <img
            src={targetThumbnailUrl}
            alt="Target"
            className="w-16 h-16 rounded-lg object-cover border border-[var(--color-border)]"
          />
          <div className="flex-1 min-w-0">
            {matchResult ? (
              <p className="text-xs text-red-400 font-[family-name:var(--font-body)] font-semibold">
                Match Found — {(matchResult.similarity * 100).toFixed(1)}%
              </p>
            ) : (
              <p className="text-xs text-[var(--color-accent)] font-[family-name:var(--font-body)] font-semibold">
                Searching...
              </p>
            )}
            <button
              onClick={handleClear}
              className="mt-1 text-xs text-red-400 hover:text-red-300 font-[family-name:var(--font-body)] cursor-pointer"
            >
              Clear Target
            </button>
          </div>
        </div>
      ) : matchResult ? (
        /* State 2: Target cleared after match — show result summary */
        <div className="flex items-start gap-3 mb-3">
          <img
            src={targetThumbnailUrl || ''}
            alt="Target"
            className="w-16 h-16 rounded-lg object-cover border border-red-500/50"
          />
          <div className="flex-1 min-w-0">
            <p className="text-xs text-red-400 font-[family-name:var(--font-body)] font-semibold">
              Match Found — {(matchResult.similarity * 100).toFixed(1)}%
            </p>
            <p className="text-[10px] text-[var(--color-muted)] font-[family-name:var(--font-body)] mt-0.5">
              Track #{matchResult.track_id} &middot; {new Date(matchResult.timestamp).toLocaleTimeString()}
            </p>
            <button
              onClick={() => { setMatchResult(null); setTargetActive(false, undefined, null) }}
              className="mt-1 text-xs text-[var(--color-muted)] hover:text-[var(--color-text)] font-[family-name:var(--font-body)] cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        </div>
      ) : (
        /* State 3: No target, no match — upload area */
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
          className="border-2 border-dashed border-[var(--color-border)] rounded-lg p-4 text-center cursor-pointer hover:border-[var(--color-muted)] transition-colors mb-3"
        >
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            className="hidden"
          />
          <p className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)]">
            {uploading ? 'Uploading...' : 'Drop target photo or click to upload'}
          </p>
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400 font-[family-name:var(--font-body)] mb-2">{error}</p>
      )}

      {/* Threshold slider */}
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <label className="text-xs text-[var(--color-muted)] font-[family-name:var(--font-body)]">
            Threshold
          </label>
          <span className="text-xs text-[var(--color-text)] font-[family-name:var(--font-heading)]">
            {targetThreshold.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min={0.3}
          max={0.8}
          step={0.01}
          value={targetThreshold}
          onChange={(e) => handleThresholdChange(parseFloat(e.target.value))}
          className="w-full h-1 bg-[var(--color-border)] rounded-lg appearance-none cursor-pointer accent-[var(--color-accent)]"
        />
        <div className="flex justify-between text-[10px] text-[var(--color-muted)] font-[family-name:var(--font-body)]">
          <span>Loose</span>
          <span>Strict</span>
        </div>
      </div>
    </div>
  )
}
