import { useMutation, useQueryClient } from '@tanstack/react-query'
import { startChatSession } from '@/features/agents/api'
import { useReplyStream } from '@/features/agents/hooks/useReplyStream'
import { queryKeys } from '@/lib/queryKeys'

/** Starts a session with its first message. It succeeds once the message is saved, and the reply then streams. */
export function useCreateChatSession() {
  const queryClient = useQueryClient()
  const { follow } = useReplyStream(undefined)
  return useMutation({
    mutationFn: startChatSession,
    onSuccess: ({ session, events }) => {
      queryClient.setQueryData(queryKeys.chatSession(session.id), session)
      void follow(session.id, events)
    },
  })
}
