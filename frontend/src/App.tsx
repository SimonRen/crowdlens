import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Dashboard } from './pages/dashboard'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] font-[family-name:var(--font-body)]">
        {/* Nav bar */}
        <nav className="bg-[var(--color-surface)] border-b border-[var(--color-border)] px-4 py-3 flex items-center">
          <h1 className="text-lg font-bold font-[family-name:var(--font-heading)] text-[var(--color-accent)]">
            CrowdLens
          </h1>
        </nav>

        <Dashboard />
      </div>
    </QueryClientProvider>
  )
}
