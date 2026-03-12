import {
  createRouter,
  createRootRoute,
  createRoute,
  Outlet,
} from '@tanstack/react-router'
import { Channels } from './pages/channels'
import { Dashboard } from './pages/dashboard'

const rootRoute = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] font-[family-name:var(--font-body)]">
      <Outlet />
    </div>
  ),
})

const channelsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: Channels,
})

const monitorRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/$channelId',
  component: Dashboard,
})

const routeTree = rootRoute.addChildren([channelsRoute, monitorRoute])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
