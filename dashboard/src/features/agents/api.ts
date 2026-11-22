import { authedFetch, SessionExpired } from '@/api/request'
import { isRecord } from '@/lib/isRecord'

/** A saved message. Only the model's replies name the model that wrote them. */
export type ChatMessage =
  | { id: number; role: 'user'; content: string }
  | { id: number; role: 'assistant'; content: string; model: string }

/** A session as the list shows it. The title is the start of its first message, or "New chat" before one. */
export type ChatSessionSummary = { id: number; title: string; updatedAt: Date }

export type ChatSession = { id: number; messages: ChatMessage[] }

const API = '/api/v1/agents/sessions'

const unexpected = () => new Error('The server sent an unexpected response.')

function parseMessage(value: unknown): ChatMessage {
  if (!isRecord(value) || typeof value.id !== 'number' || typeof value.content !== 'string') throw unexpected()
  const { id, content } = value
  if (value.role === 'user') return { id, role: 'user', content }
  if (value.role === 'assistant' && typeof value.model === 'string') return { id, role: 'assistant', content, model: value.model }
  throw unexpected()
}

function parseSession(value: unknown): ChatSession {
  if (!isRecord(value) || typeof value.id !== 'number' || !Array.isArray(value.messages)) throw unexpected()
  return { id: value.id, messages: value.messages.map(parseMessage) }
}

function parseSummary(value: unknown): ChatSessionSummary {
  if (!isRecord(value) || typeof value.id !== 'number' || typeof value.updated_at !== 'string') throw unexpected()
  if (value.title !== null && typeof value.title !== 'string') throw unexpected()
  return { id: value.id, title: value.title ?? 'New chat', updatedAt: new Date(value.updated_at) }
}

/** Sends a request as the signed-in user. Null means the session does not exist. Throws an Error to show the user. */
async function send(path: string, init: RequestInit, action: string): Promise<unknown> {
  const res = await authedFetch(`${API}${path}`, init)
  if (!res) throw new Error('Cannot reach the server. Check that the API server is running.')
  if (res.status === 401) throw new SessionExpired()
  if (res.status === 404) return null
  const body: unknown = res.status === 204 ? undefined : await res.json().catch(() => undefined)
  if (res.ok) return body
  throw new Error(isRecord(body) && typeof body.detail === 'string' ? body.detail : `The server could not ${action} (HTTP ${res.status}).`)
}

const post = (body?: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body ?? {}),
})

const gone = () => new Error('This chat no longer exists.')

export async function listChatSessions(): Promise<ChatSessionSummary[]> {
  const body = await send('/', {}, 'load your chats')
  if (!Array.isArray(body)) throw unexpected()
  return body.map(parseSummary)
}

/** The session with its messages, or null when the signed-in user has no session with this id. */
export async function getChatSession(id: number): Promise<ChatSession | null> {
  const body = await send(`/${id}/`, {}, 'load the chat')
  return body === null ? null : parseSession(body)
}

/** Sends a message in a session. Returns the saved message and the model's reply. */
export async function sendChatMessage(sessionId: number, content: string): Promise<ChatMessage[]> {
  const body = await send(`/${sessionId}/messages/`, post({ content }), 'send the message')
  if (body === null) throw gone()
  if (!isRecord(body) || !Array.isArray(body.messages)) throw unexpected()
  return body.messages.map(parseMessage)
}

/**
 * Starts a session with its first message. When the message fails, it deletes the new session again, so a failed
 * first message leaves no empty session behind.
 */
export async function startChatSession(content: string): Promise<ChatSession> {
  const session = parseSession(await send('/', post(), 'start a chat'))
  try {
    return { ...session, messages: await sendChatMessage(session.id, content) }
  } catch (error) {
    await deleteChatSession(session.id).catch(() => undefined)
    throw error
  }
}

export async function deleteChatSession(id: number): Promise<void> {
  if ((await send(`/${id}/`, { method: 'DELETE' }, 'delete the chat')) === null) throw gone()
}
