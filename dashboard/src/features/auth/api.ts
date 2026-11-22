import { authedFetch } from '@/api/request'
import { clearSession, loadSession, parseSession, saveSession } from '@/api/session'
import { isRecord } from '@/lib/isRecord'

export type User = { email: string }

/** Who is signed in. The tokens stay in storage, which src/api/session.ts owns. */
export type SignedIn = { user: User }

const API = '/api/v1/auth'

export function signOut() {
  clearSession()
}

async function post(path: string, body: unknown): Promise<Response | null> {
  try {
    return await fetch(`${API}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    return null
  }
}

/** Loads the user for the stored session, refreshing the access token once if it expired. Null means sign in again. */
async function getMe(): Promise<User | null> {
  const res = await authedFetch(`${API}/me/`)
  if (!res?.ok) return null
  const body: unknown = await res.json().catch(() => null)
  return isRecord(body) && typeof body.email === 'string' ? { email: body.email } : null
}

/** Restores the stored session on page load. Null means nobody is signed in. */
export async function restoreSession(): Promise<SignedIn | null> {
  if (!loadSession()) return null
  const user = await getMe()
  if (!user) clearSession()
  return user && { user }
}

/** Signs in and stores the session. Throws an Error with a message to show the user. */
export async function signIn(email: string, password: string): Promise<SignedIn> {
  const res = await post('/token/', { email, password })
  if (!res) throw new Error('Cannot reach the server. Check that the API server is running.')
  if (res.status === 401) throw new Error('The email or password is incorrect.')
  if (!res.ok) throw new Error(`The server could not sign you in (HTTP ${res.status}).`)
  const session = parseSession(await res.json().catch(() => null))
  if (!session) throw new Error('The server sent an unexpected response.')
  saveSession(session)
  const user = await getMe()
  if (!user) {
    clearSession()
    throw new Error('Signed in, but the server could not load your account.')
  }
  return { user }
}
