import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Dashboard } from './pages/dashboard'
import { History } from './pages/history'

const queryClient = new QueryClient()

type Page = 'dashboard' | 'history'

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] font-[family-name:var(--font-body)]">
        {/* Nav bar */}
        <nav className="bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-bold font-[family-name:var(--font-heading)] text-[var(--color-accent)]">
            Live Monitor
          </h1>
          <div className="flex gap-1">
            <button
              onClick={() => setPage('dashboard')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium cursor-pointer transition-colors duration-200 ${
                page === 'dashboard'
                  ? 'bg-[var(--color-accent)]/10 text-[var(--color-accent)]'
                  : 'text-[var(--color-muted)] hover:text-[var(--color-text)]'
              }`}
            >
              Dashboard
            </button>
            <button
              onClick={() => setPage('history')}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium cursor-pointer transition-colors duration-200 ${
                page === 'history'
                  ? 'bg-[var(--color-accent)]/10 text-[var(--color-accent)]'
                  : 'text-[var(--color-muted)] hover:text-[var(--color-text)]'
              }`}
            >
              History
            </button>
          </div>
        </nav>

        {/* Page content */}
        {page === 'dashboard' ? <Dashboard /> : <History />}
      </div>
    </QueryClientProvider>
  )
}
