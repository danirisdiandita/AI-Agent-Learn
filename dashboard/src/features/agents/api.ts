import { authedFetch, SessionExpired } from '@/api/request'
import { isRecord } from '@/lib/isRecord'

/** An event the model wants to add to the user's Google Calendar. Start and end are wall-clock times in `timeZone`. */
export type CalendarEvent = { summary: string; start: string; end: string; timeZone: string; description: string | null }

/** Where a tool call stands. Approved lasts while the tool runs, and stays when the server stopped before it finished. */
export type ToolCallOutcome =
  | { status: 'pending' }
  | { status: 'approved' }
  | { status: 'declined' }
  | { status: 'succeeded'; link: string | null }
  | { status: 'failed'; error: string }

/** A tool call the model asked for. `event` is null when the arguments are not a calendar event. */
export type ToolCall = { id: number; name: string; event: CalendarEvent | null; outcome: ToolCallOutcome }

/** A saved message. Only the model's replies name the model that wrote them, and only they call tools. */
export type ChatMessage =
  | { id: number; role: 'user'; content: string }
  | { id: number; role: 'assistant'; content: string; model: string; toolCalls: ToolCall[] }

/** A session as the list shows it. The title is the start of its first message, or "New chat" before one. */
export type ChatSessionSummary = { id: number; title: string; updatedAt: Date }

export type ChatSession = { id: number; messages: ChatMessage[] }

/** What the server streams while the model replies. The stream ends after an error, or when the reply is done. */
export type ChatEvent =
  | { type: 'delta'; text: string }
  | { type: 'message'; message: ChatMessage }
  | { type: 'tool_call'; call: ToolCall }
  | { type: 'error'; detail: string }

export type ChatStream = AsyncGenerator<ChatEvent, void>

/** The model's reply in a session while it streams, or why it stopped. */
export type ReplyState = { phase: 'streaming'; text: string } | { phase: 'failed'; error: string }

const API = '/api/v1/agents'

const unexpected = () => new Error('The server sent an unexpected response.')

const text = (value: unknown) => (typeof value === 'string' ? value : null)

// A wall-clock date-time without an offset, as the server stores calendar events: 2026-11-23T15:00:00.
const WALL_CLOCK = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/

function parseEvent(value: unknown): CalendarEvent | null {
  if (!isRecord(value)) return null
  const [summary, start, end, timeZone] = [text(value.summary), text(value.start), text(value.end), text(value.time_zone)]
  if (!summary || !start || !end || !timeZone || !WALL_CLOCK.test(start) || !WALL_CLOCK.test(end)) return null
  return { summary, start, end, timeZone, description: text(value.description) }
}

function parseOutcome(status: unknown, result: unknown): ToolCallOutcome {
  if (status === 'pending' || status === 'approved' || status === 'declined') return { status }
  if (status === 'succeeded') {
    const link = isRecord(result) ? text(result.html_link) : null
    return { status, link: link?.startsWith('https://') ? link : null }
  }
  if (status === 'failed') return { status, error: (isRecord(result) && text(result.error)) || 'The tool call failed.' }
  throw unexpected()
}

function parseToolCall(value: unknown): ToolCall {
  if (!isRecord(value) || typeof value.id !== 'number' || typeof value.name !== 'string') throw unexpected()
  return {
    id: value.id,
    name: value.name,
    event: value.name === 'create_calendar_event' ? parseEvent(value.arguments) : null,
    outcome: parseOutcome(value.status, value.result),
  }
}

function parseMessage(value: unknown): ChatMessage {
  if (!isRecord(value) || typeof value.id !== 'number' || typeof value.content !== 'string') throw unexpected()
  const { id, content } = value
  if (value.role === 'user') return { id, role: 'user', content }
  if (value.role === 'assistant' && typeof value.model === 'string' && Array.isArray(value.tool_calls)) {
    return { id, role: 'assistant', content, model: value.model, toolCalls: value.tool_calls.map(parseToolCall) }
  }
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

/** Sends a request as the signed-in user. Null means the target does not exist. Throws an Error to show the user. */
async function request(path: string, init: RequestInit, action: string): Promise<Response | null> {
  const res = await authedFetch(`${API}${path}`, init)
  if (!res) throw new Error('Cannot reach the server. Check that the API server is running.')
  if (res.status === 401) throw new SessionExpired()
  if (res.status === 404) return null
  if (res.ok) return res
  const body: unknown = await res.json().catch(() => undefined)
  throw new Error(isRecord(body) && typeof body.detail === 'string' ? body.detail : `The server could not ${action} (HTTP ${res.status}).`)
}

async function send(path: string, init: RequestInit, action: string): Promise<unknown> {
  const res = await request(path, init, action)
  if (res === null) return null
  return res.status === 204 ? undefined : await res.json().catch(() => undefined)
}

const post = (body?: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body ?? {}),
})

const gone = () => new Error('This chat no longer exists.')

// The model reads the user's local time from this, so "tomorrow at 3pm" means the user's 3pm.
const timeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone

/** One server-sent event as a ChatEvent, 'done' at the end of the stream, or null for an event this client skips. */
function parseServerEvent(block: string): ChatEvent | 'done' | null {
  let name = ''
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) name = line.slice(7)
    else if (line.startsWith('data: ')) data += line.slice(6)
  }
  const payload: unknown = JSON.parse(data || 'null')
  switch (name) {
    case 'delta':
      return isRecord(payload) && typeof payload.text === 'string' ? { type: 'delta', text: payload.text } : null
    case 'user_message':
    case 'assistant_message':
      return { type: 'message', message: parseMessage(payload) }
    case 'tool_call':
      return { type: 'tool_call', call: parseToolCall(payload) }
    case 'error':
      return { type: 'error', detail: (isRecord(payload) && text(payload.detail)) || 'The model did not reply.' }
    case 'done':
      return 'done'
    default:
      return null
  }
}

/** The events of a streamed response. A stream that ends before the server said it is done ends with an error. */
async function* readEvents(res: Response): ChatStream {
  const reader = res.body?.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (reader) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      for (let end = buffer.indexOf('\n\n'); end !== -1; end = buffer.indexOf('\n\n')) {
        const event = parseServerEvent(buffer.slice(0, end))
        buffer = buffer.slice(end + 2)
        if (event === 'done') return
        if (event) yield event
        if (event?.type === 'error') return
      }
    }
  } catch (error) {
    if (!(error instanceof TypeError)) throw error
  }
  yield { type: 'error', detail: 'The connection to the server broke off before the reply finished.' }
}

/** Opens a streamed request and reads its first event, which is the record of what the user just did. */
async function openStream(path: string, body: unknown, action: string): Promise<{ first: ChatEvent; events: ChatStream }> {
  const res = await request(path, post(body), action)
  if (res === null) throw gone()
  const events = readEvents(res)
  const first = await events.next()
  if (first.done) throw unexpected()
  if (first.value.type === 'error') throw new Error(first.value.detail)
  return { first: first.value, events }
}

export async function listChatSessions(): Promise<ChatSessionSummary[]> {
  const body = await send('/sessions/', {}, 'load your chats')
  if (!Array.isArray(body)) throw unexpected()
  return body.map(parseSummary)
}

/** The session with its messages, or null when the signed-in user has no session with this id. */
export async function getChatSession(id: number): Promise<ChatSession | null> {
  const body = await send(`/sessions/${id}/`, {}, 'load the chat')
  return body === null ? null : parseSession(body)
}

/**
 * Sends a message in a session. Resolves once the server saved it, with the saved message and the stream of the
 * model's reply. Throws when the server refused the message, and then nothing was saved.
 */
export async function sendChatMessage(sessionId: number, content: string): Promise<{ message: ChatMessage; events: ChatStream }> {
  const { first, events } = await openStream(`/sessions/${sessionId}/messages/`, { content, time_zone: timeZone() }, 'send the message')
  if (first.type !== 'message') throw unexpected()
  return { message: first.message, events }
}

/** Asks the model to reply to the session as it stands, such as after a reply that failed. */
export async function retryReply(sessionId: number): Promise<ChatStream> {
  const res = await request(`/sessions/${sessionId}/reply/`, post({ time_zone: timeZone() }), 'ask the model again')
  if (res === null) throw gone()
  return readEvents(res)
}

/**
 * Approves or declines a tool call. Resolves once the server saved the decision and, after an approval, ran the tool,
 * with the decided call and the stream of the model's follow-up.
 */
export async function decideToolCall(callId: number, approve: boolean): Promise<{ call: ToolCall; events: ChatStream }> {
  const { first, events } = await openStream(`/tool-calls/${callId}/decision/`, { approve, time_zone: timeZone() }, 'save your decision')
  if (first.type !== 'tool_call') throw unexpected()
  return { call: first.call, events }
}

/**
 * Starts a session with its first message. When the server refuses the message, it deletes the new session again, so
 * a refused first message leaves no empty session behind.
 */
export async function startChatSession(content: string): Promise<{ session: ChatSession; events: ChatStream }> {
  const session = parseSession(await send('/sessions/', post(), 'start a chat'))
  try {
    const { message, events } = await sendChatMessage(session.id, content)
    return { session: { ...session, messages: [message] }, events }
  } catch (error) {
    await deleteChatSession(session.id).catch(() => undefined)
    throw error
  }
}

export async function deleteChatSession(id: number): Promise<void> {
  if ((await send(`/sessions/${id}/`, { method: 'DELETE' }, 'delete the chat')) === null) throw gone()
}
