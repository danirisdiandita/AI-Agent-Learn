export type ChatMessage = { role: 'user' | 'assistant'; content: string }

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null

/** The access token in the cached session, or null when nobody is signed in. */
export const accessToken = (session: unknown): string | null =>
  isRecord(session) && isRecord(session.session) && typeof session.session.access === 'string'
    ? session.session.access
    : null

/** Thrown when the access token expired, so the caller can renew the session and retry. */
export class Unauthorized extends Error {}

/** Sends the conversation and returns the model's reply. Throws an Error with a message to show the user. */
export async function sendChat(access: string, messages: ChatMessage[]): Promise<ChatMessage> {
  let res: Response
  try {
    res = await fetch('/api/v1/agents/chat/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${access}` },
      body: JSON.stringify({ messages }),
    })
  } catch {
    throw new Error('Cannot reach the server. Check that the API server is running.')
  }
  if (res.status === 401) throw new Unauthorized('Your session expired. Sign in again.')
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) {
    throw new Error(isRecord(body) && typeof body.detail === 'string' ? body.detail : `The chat failed (HTTP ${res.status}).`)
  }
  const message = isRecord(body) && isRecord(body.message) ? body.message : null
  if (!message || message.role !== 'assistant' || typeof message.content !== 'string') {
    throw new Error('The server sent an unexpected response.')
  }
  return { role: 'assistant', content: message.content }
}
