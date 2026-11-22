import { authedFetch, SessionExpired } from '@/api/request'
import { isRecord } from '@/lib/isRecord'

/** Where an integration stands for the signed-in user. A connection shows even if the server lost its client. */
export type IntegrationState =
  | { kind: 'connected'; accountEmail: string; connectedAt: Date }
  | { kind: 'disconnected' }
  | { kind: 'unconfigured' }

export type Integration = { id: string; name: string; description: string; state: IntegrationState }

const API = '/api/v1/integrations'

const unexpected = () => new Error('The server sent an unexpected response.')

function parseState(configured: unknown, connection: unknown): IntegrationState {
  if (isRecord(connection)) {
    const { account_email: accountEmail, connected_at: connectedAt } = connection
    if (typeof accountEmail !== 'string' || typeof connectedAt !== 'string') throw unexpected()
    return { kind: 'connected', accountEmail, connectedAt: new Date(connectedAt) }
  }
  if (connection !== null || typeof configured !== 'boolean') throw unexpected()
  return configured ? { kind: 'disconnected' } : { kind: 'unconfigured' }
}

function parseIntegration(value: unknown): Integration {
  if (!isRecord(value)) throw unexpected()
  const { id, name, description } = value
  if (typeof id !== 'string' || typeof name !== 'string' || typeof description !== 'string') throw unexpected()
  return { id, name, description, state: parseState(value.configured, value.connection) }
}

/** Sends a request as the signed-in user. Throws an Error with a message to show when it does not succeed. */
async function send(path: string, init: RequestInit, action: string): Promise<Response> {
  const res = await authedFetch(`${API}${path}`, init)
  if (!res) throw new Error('Cannot reach the server. Check that the API server is running.')
  if (res.status === 401) throw new SessionExpired()
  if (res.ok) return res
  const body: unknown = await res.json().catch(() => null)
  const detail = isRecord(body) && typeof body.detail === 'string' ? ` ${body.detail}` : ''
  throw new Error(`The server could not ${action} (HTTP ${res.status}).${detail}`)
}

export async function listIntegrations(): Promise<Integration[]> {
  const res = await send('/', {}, 'load the integrations')
  const body: unknown = await res.json().catch(() => null)
  if (!Array.isArray(body)) throw unexpected()
  return body.map(parseIntegration)
}

/** Starts a connection. Returns the provider's page where the user grants access. */
export async function connectIntegration(id: string): Promise<string> {
  const res = await send(`/${id}/connect/`, { method: 'POST' }, 'start the connection')
  const body: unknown = await res.json().catch(() => null)
  if (!isRecord(body) || typeof body.authorization_url !== 'string') throw unexpected()
  return body.authorization_url
}

export async function disconnectIntegration(id: string): Promise<void> {
  await send(`/${id}/`, { method: 'DELETE' }, 'disconnect the account')
}
