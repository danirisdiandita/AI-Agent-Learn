import { useQueryClient } from '@tanstack/react-query'
import { create } from 'zustand'
import type { ChatEvent, ChatMessage, ChatSession, ChatStream, ReplyState, ToolCall } from '@/features/agents/api'
import { queryKeys } from '@/lib/queryKeys'

// The reply in each session while it streams, by session id. It lives outside every component, so a reply keeps
// streaming while the screen changes, such as when a new chat moves to its own address.
const replies = create<Record<number, ReplyState | undefined>>()(() => ({}))

const setReply = (sessionId: number, reply: ReplyState | undefined) => replies.setState({ [sessionId]: reply })

function addMessage(session: ChatSession, message: ChatMessage): ChatSession {
  return { ...session, messages: [...session.messages.filter((m) => m.id !== message.id), message] }
}

function replaceCall(session: ChatSession, call: ToolCall): ChatSession {
  return {
    ...session,
    messages: session.messages.map((m) =>
      m.role === 'assistant' && m.toolCalls.some((c) => c.id === call.id)
        ? { ...m, toolCalls: m.toolCalls.map((c) => (c.id === call.id ? call : c)) }
        : m,
    ),
  }
}

/**
 * The model's reply in a session while it streams, or why it stopped, and `follow`, which reads a reply's stream into
 * the session's cached messages. `first` holds events the caller already read, such as the saved user message.
 */
export function useReplyStream(sessionId: number | undefined) {
  const queryClient = useQueryClient()
  const reply = replies((state) => (sessionId === undefined ? undefined : state[sessionId]))

  const apply = (id: number, event: Exclude<ChatEvent, { type: 'error' }>) => {
    const update = (change: (session: ChatSession) => ChatSession) =>
      queryClient.setQueryData<ChatSession | null>(queryKeys.chatSession(id), (session) => session && change(session))
    switch (event.type) {
      case 'delta': {
        const current = replies.getState()[id]
        setReply(id, { phase: 'streaming', text: (current?.phase === 'streaming' ? current.text : '') + event.text })
        return
      }
      case 'message':
        update((session) => addMessage(session, event.message))
        // A reply that calls tools that need no approval goes on with another step.
        if (event.message.role === 'assistant') setReply(id, { phase: 'streaming', text: '' })
        return
      case 'tool_call':
        update((session) => replaceCall(session, event.call))
    }
  }

  const follow = async (id: number, events: ChatStream, ...first: ChatEvent[]) => {
    const refreshList = () => queryClient.invalidateQueries({ queryKey: queryKeys.chatSessions, exact: true })
    setReply(id, { phase: 'streaming', text: '' })
    try {
      for (const event of first) if (event.type !== 'error') apply(id, event)
      void refreshList()
      for await (const event of events) {
        if (event.type === 'error') {
          setReply(id, { phase: 'failed', error: event.detail })
          return
        }
        apply(id, event)
      }
      setReply(id, undefined)
    } catch (error) {
      setReply(id, { phase: 'failed', error: error instanceof Error ? error.message : 'The model did not reply.' })
    } finally {
      // The list orders sessions by their latest message, and takes the title from the first.
      void refreshList()
    }
  }

  return { reply, follow }
}
