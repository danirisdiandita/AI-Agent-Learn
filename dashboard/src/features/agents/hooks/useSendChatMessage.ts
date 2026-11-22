import { useMutation } from '@tanstack/react-query'
import { sendChatMessage } from '@/features/agents/api'
import { useReplyStream } from '@/features/agents/hooks/useReplyStream'

/**
 * Sends a message in a session that already exists. The mutation lasts until the server saved the message, so its
 * error means nothing was saved. The reply then streams through useReplyStream.
 */
export function useSendChatMessage(sessionId: number) {
  const { follow } = useReplyStream(sessionId)
  return useMutation({
    mutationFn: (content: string) => sendChatMessage(sessionId, content),
    onSuccess: ({ message, events }) => void follow(sessionId, events, { type: 'message', message }),
  })
}
