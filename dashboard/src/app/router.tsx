import type { QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, createRoute, createRouter, redirect } from '@tanstack/react-router'
import { AppShell } from '@/app/shell/AppShell'
import { PlannedSection } from '@/app/shell/EmptyState'
import { NotFound } from '@/app/shell/NotFound'
import type { PlannedSection as Planned } from '@/app/shell/sections'
import { restoreSession } from '@/features/auth/api'
import { SignInPage } from '@/features/auth/components/SignInPage'
import { AgentsPage } from '@/features/agents/components/AgentsPage'
import { NewChat } from '@/features/agents/components/NewChat'
import { SessionChat } from '@/features/agents/components/SessionChat'
import { IntegrationsPage } from '@/features/integrations/components/IntegrationsPage'
import { queryKeys } from '@/lib/queryKeys'

// The session query is the only record of who is signed in. Sign-in and sign-out write it in the cache.
const session = (queryClient: QueryClient) =>
  queryClient.query({ queryKey: queryKeys.session, queryFn: restoreSession, staleTime: Infinity })

// A redirect target must stay on this origin: a path such as /runs, never //evil.example or a full URL.
const isSafeRedirect = (value: unknown): value is string =>
  typeof value === 'string' && value.startsWith('/') && new URL(value, location.origin).origin === location.origin

const rootRoute = createRootRouteWithContext<{ queryClient: QueryClient }>()()

const signInRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/sign-in',
  // Set redirect even when it is unsafe: the router lays the validated search over the raw query string,
  // so a key left out keeps its raw value.
  validateSearch: (search): { redirect?: string } => ({
    redirect: isSafeRedirect(search.redirect) ? search.redirect : undefined,
  }),
  beforeLoad: async ({ context, search }) => {
    if (await session(context.queryClient)) throw redirect({ href: search.redirect ?? '/agents' })
  },
  component: SignInPage,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/agents' })
  },
})

// Every screen except sign-in sits in the shell, and only a signed-in user reaches it.
const signedInRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'signed-in',
  beforeLoad: async ({ context, location }) => {
    const signedIn = await session(context.queryClient)
    if (!signedIn) throw redirect({ to: '/sign-in', search: { redirect: location.href } })
    return { user: signedIn.user }
  },
  component: AppShell,
})

// /agents lists the chats beside a new chat, and /agents/<id> beside a saved one. Only a positive integer matches $sessionId,
// so a path such as /agents/no-such-chat falls through to the not-found page.
const agentsRoute = createRoute({ getParentRoute: () => signedInRoute, path: '/agents', component: AgentsPage })
const agentsRoutes = agentsRoute.addChildren([
  createRoute({ getParentRoute: () => agentsRoute, path: '/', component: NewChat }),
  createRoute({
    getParentRoute: () => agentsRoute,
    path: '$sessionId',
    params: {
      parse: ({ sessionId }) =>
        /^[1-9]\d*$/.test(sessionId) && Number.isSafeInteger(Number(sessionId)) ? { sessionId: Number(sessionId) } : false,
      stringify: ({ sessionId }) => ({ sessionId: String(sessionId) }),
    },
    component: SessionChat,
  }),
])

// A section whose feature is not built yet. Its route shows the section's empty state.
const plannedSection = <TPath extends Planned['path']>(path: TPath) =>
  createRoute({ getParentRoute: () => signedInRoute, path, component: PlannedSection })

const routeTree = rootRoute.addChildren([
  signInRoute,
  indexRoute,
  signedInRoute.addChildren([
    agentsRoutes,
    plannedSection('/runs'),
    plannedSection('/tools'),
    plannedSection('/knowledge'),
    createRoute({
      getParentRoute: () => signedInRoute,
      path: '/integrations',
      // The connect callback lands here with ?connected=<id> or ?error=<code>. Return every key: one left out
      // keeps its raw value.
      validateSearch: (search): { connected?: string; error?: string } => ({
        connected: typeof search.connected === 'string' ? search.connected : undefined,
        error: typeof search.error === 'string' ? search.error : undefined,
      }),
      component: IntegrationsPage,
    }),
    // Any other path, so a signed-in user sees the not-found page inside the shell.
    createRoute({ getParentRoute: () => signedInRoute, path: '$', component: NotFound }),
  ]),
])

export function createAppRouter(queryClient: QueryClient) {
  return createRouter({ routeTree, context: { queryClient } })
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}
