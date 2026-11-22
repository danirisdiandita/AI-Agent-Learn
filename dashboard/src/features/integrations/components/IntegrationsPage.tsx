import { useNavigate, useSearch } from '@tanstack/react-router'
import { CalendarDays, CircleCheck, Plug, X, type LucideIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { Integration, IntegrationState } from '@/features/integrations/api'
import { useConnectIntegration } from '@/features/integrations/hooks/useConnectIntegration'
import { useDisconnectIntegration } from '@/features/integrations/hooks/useDisconnectIntegration'
import { useIntegrations } from '@/features/integrations/hooks/useIntegrations'

// How each integration from the server shows here. One the dashboard does not know yet shows with a plug icon.
const known = new Map<string, { icon: LucideIcon; settings: string[] }>([
  ['google-calendar', { icon: CalendarDays, settings: ['GOOGLE_OAUTH_CLIENT_ID', 'GOOGLE_OAUTH_CLIENT_SECRET'] }],
])

// The codes the server's callback sends back in ?error=. A Map, because the code comes from the address bar.
const failures = new Map([
  ['denied', 'Access was not granted, so nothing was connected.'],
  ['expired', 'The connection request expired or was not valid. Connect again.'],
  ['failed', 'The provider did not complete the connection. Try again.'],
  ['not_configured', 'This integration is not configured on the server.'],
])

const dot = { connected: 'bg-[var(--success)]', disconnected: 'bg-[var(--text-4)]', unconfigured: 'bg-[var(--warning)]' }

export function IntegrationsPage() {
  const { connected, error } = useSearch({ from: '/signed-in/integrations' })
  const integrations = useIntegrations()
  return (
    <div className="flex w-full max-w-3xl flex-col gap-6 p-4 sm:p-6">
      <p className="max-w-[640px] text-muted-foreground">
        Connect accounts from other services for your agents to work with. Agent tools that use these connections are
        planned.
      </p>
      {error !== undefined ? (
        <Notice tone="danger">{failures.get(error) ?? 'The connection did not complete. Try again.'}</Notice>
      ) : connected !== undefined ? (
        <Notice tone="success">
          {`${integrations.data?.find((i) => i.id === connected)?.name ?? 'The account'} is connected.`}
        </Notice>
      ) : null}
      {integrations.isPending ? (
        <CardSkeleton />
      ) : integrations.isError ? (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-[var(--danger-text)]">
          {integrations.error.message}
          <Button variant="secondary" size="sm" onClick={() => integrations.refetch()}>
            Try again
          </Button>
        </div>
      ) : (
        <ul className="flex flex-col gap-4">
          {integrations.data.map((integration) => (
            <IntegrationCard key={integration.id} integration={integration} />
          ))}
        </ul>
      )}
    </div>
  )
}

function Notice({ tone, children }: { tone: 'success' | 'danger'; children: string }) {
  const navigate = useNavigate()
  const dismiss = () => navigate({ to: '/integrations', search: {}, replace: true })
  return (
    <div
      role={tone === 'danger' ? 'alert' : 'status'}
      className={
        tone === 'danger'
          ? 'flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 py-1.5 pr-1.5 pl-3 text-sm text-[var(--danger-text)]'
          : 'flex items-center gap-2 rounded-md border border-[color-mix(in_srgb,var(--success)_30%,transparent)] bg-[color-mix(in_srgb,var(--success)_10%,transparent)] py-1.5 pr-1.5 pl-3 text-sm text-foreground'
      }
    >
      {tone === 'success' && <CircleCheck aria-hidden="true" className="size-4 shrink-0 text-[var(--success)]" />}
      <p className="flex-1 py-1">{children}</p>
      <Button variant="ghost" size="icon-sm" aria-label="Dismiss" onClick={dismiss}>
        <X aria-hidden="true" />
      </Button>
    </div>
  )
}

function IntegrationCard({ integration }: { integration: Integration }) {
  const { icon: Icon, settings } = known.get(integration.id) ?? { icon: Plug, settings: [] }
  const connect = useConnectIntegration()
  const disconnect = useDisconnectIntegration()
  const { state } = integration
  // After a successful connect the browser is on its way to the provider, so the button stays busy.
  const leaving = connect.isPending || connect.isSuccess
  const failed = connect.error ?? disconnect.error
  return (
    <li className="flex flex-col gap-4 rounded-xl border bg-card p-6 shadow-[var(--highlight)] transition-colors hover:border-[var(--border-strong)] sm:flex-row sm:items-start">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-muted">
        <Icon aria-hidden="true" className="size-4 text-foreground" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <h2 className="text-xl font-[560] tracking-[-0.012em]">{integration.name}</h2>
        <p className="text-muted-foreground">{integration.description}</p>
        <p className="mt-2 flex items-baseline gap-2 text-sm text-[var(--text-2)]">
          <span aria-hidden="true" className={`dot translate-y-[-1px] ${dot[state.kind]}`} />
          <span className="min-w-0">
            <Status state={state} settings={settings} />
          </span>
        </p>
        {failed && (
          <p role="alert" className="mt-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-[var(--danger-text)]">
            {failed.message}
          </p>
        )}
      </div>
      {state.kind === 'connected' ? (
        <Button
          variant="secondary"
          className="w-full sm:w-auto"
          disabled={disconnect.isPending}
          onClick={() => {
            connect.reset()
            disconnect.mutate(integration.id)
          }}
        >
          {disconnect.isPending ? 'Disconnecting…' : 'Disconnect'}
        </Button>
      ) : (
        <Button
          className="w-full sm:w-auto"
          disabled={state.kind === 'unconfigured' || leaving}
          onClick={() => {
            disconnect.reset()
            connect.mutate(integration.id)
          }}
        >
          {leaving ? 'Redirecting…' : 'Connect'}
        </Button>
      )}
    </li>
  )
}

function Status({ state, settings }: { state: IntegrationState; settings: string[] }) {
  switch (state.kind) {
    case 'connected':
      return (
        <>
          Connected as <span className="font-[560] wrap-anywhere text-foreground">{state.accountEmail}</span> since{' '}
          {state.connectedAt.toLocaleDateString(undefined, { dateStyle: 'medium' })}
        </>
      )
    case 'disconnected':
      return 'Not connected'
    case 'unconfigured':
      return settings.length ? (
        <>
          Not configured: set{' '}
          {settings.map((name, i) => (
            <span key={name}>
              {i > 0 && ' and '}
              <code className="font-[family-name:var(--font-monospace)] wrap-anywhere text-foreground">{name}</code>
            </span>
          ))}{' '}
          on the server
        </>
      ) : (
        'Not configured on this server'
      )
  }
}

function CardSkeleton() {
  return (
    <div aria-busy="true" className="flex flex-col gap-4 rounded-xl border bg-card p-6 sm:flex-row sm:items-start">
      <span className="sr-only">Loading integrations</span>
      <Skeleton className="size-8 shrink-0" />
      <div className="flex flex-1 flex-col gap-2">
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-4 w-full max-w-80" />
        <Skeleton className="mt-2 h-4 w-32" />
      </div>
      <Skeleton className="h-9 w-full sm:w-24" />
    </div>
  )
}
