import { isRecord } from '@/lib/isRecord'

/** The signed-in user's JWT pair. It lives in localStorage, and only src/api/ and sign-in read or write it. */
export type Session = { access: string; refresh: string }

const STORAGE_KEY = 'nextsci-agents.session'

/** A session from a server response or from storage, or null when the value is not one. */
export function parseSession(value: unknown): Session | null {
  return isRecord(value) && typeof value.access === 'string' && typeof value.refresh === 'string'
    ? { access: value.access, refresh: value.refresh }
    : null
}

export function loadSession(): Session | null {
  try {
    return parseSession(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null'))
  } catch {
    return null
  }
}

export function saveSession(session: Session) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEY)
}
