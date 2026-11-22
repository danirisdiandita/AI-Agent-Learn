import { loadSession, saveSession, type Session } from '@/api/session'
import { isRecord } from '@/lib/isRecord'

/**
 * Thrown by an API module when the server answers 401 even after authedFetch refreshed the token, so the refresh token
 * expired too. The query client in main.tsx catches it and sends the user to sign-in.
 */
export class SessionExpired extends Error {
  constructor() {
    super('Your session expired. Sign in again.')
  }
}

async function refreshSession(session: Session): Promise<Session | null> {
  const res = await fetch('/api/v1/auth/token/refresh/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh: session.refresh }),
  })
  if (!res.ok) return null
  const body: unknown = await res.json().catch(() => null)
  return isRecord(body) && typeof body.access === 'string' ? { ...session, access: body.access } : null
}

/**
 * Calls the API as the signed-in user, with the stored access token. When the server answers 401, it refreshes
 * the token once, saves it, and retries. Null means the server could not be reached.
 */
export async function authedFetch(path: string, init: RequestInit = {}): Promise<Response | null> {
  const send = (session: Session | null) => {
    const headers = new Headers(init.headers)
    if (session) headers.set('Authorization', `Bearer ${session.access}`)
    return fetch(path, { ...init, headers })
  }
  try {
    const session = loadSession()
    const res = await send(session)
    if (res.status !== 401 || !session) return res
    const renewed = await refreshSession(session)
    if (!renewed) return res
    saveSession(renewed)
    return await send(renewed)
  } catch {
    return null
  }
}
