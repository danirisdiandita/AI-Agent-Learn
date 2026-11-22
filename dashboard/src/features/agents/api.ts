import { authedFetch } from '@/api/request'
import { isRecord } from '@/lib/isRecord'

export type ChatMessage = { role: 'user' | 'assistant'; content: string }

/** Thrown when the session ended: the access token expired and refreshing it failed. */
export class Unauthorized extends Error {}

/** Sends the conversation and returns the model's reply. Throws an Error with a message to show the user. */
export async function sendChat(messages: ChatMessage[]): Promise<ChatMessage> {
  const res = await authedFetch('/api/v1/agents/chat/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
  })
  if (!res) throw new Error('Cannot reach the server. Check that the API server is running.')
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
