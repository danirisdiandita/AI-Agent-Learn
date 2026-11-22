import { useNavigate } from '@tanstack/react-router'
import { ChatPanel } from '@/features/agents/components/ChatPanel'
import { useCreateChatSession } from '@/features/agents/hooks/useCreateChatSession'

/**
 * /agents: a chat with no session yet. The first message saves one, and the address moves to it once the server saved
 * the message. The reply keeps streaming on the session's own screen.
 */
export function NewChat() {
  const create = useCreateChatSession()
  const navigate = useNavigate()
  return (
    <ChatPanel
      // Keep showing the saved message until the session's own screen takes over.
      messages={create.data?.session.messages ?? []}
      sending={create.isPending ? create.variables : null}
      error={create.error?.message ?? null}
      onSend={(content, { onError }) =>
        create.mutate(content, {
          onError,
          onSuccess: ({ session }) => navigate({ to: '/agents/$sessionId', params: { sessionId: session.id }, replace: true }),
        })
      }
    />
  )
}
