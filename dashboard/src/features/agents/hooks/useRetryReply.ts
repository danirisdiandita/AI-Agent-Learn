import { useMutation } from '@tanstack/react-query'
import { retryReply } from '@/features/agents/api'
import { useReplyStream } from '@/features/agents/hooks/useReplyStream'

/** Asks the model again to answer a session whose reply failed. */
export function useRetryReply(sessionId: number) {
  const { follow } = useReplyStream(sessionId)
  return useMutation({
    mutationFn: () => retryReply(sessionId),
    onSuccess: (events) => void follow(sessionId, events),
  })
}
