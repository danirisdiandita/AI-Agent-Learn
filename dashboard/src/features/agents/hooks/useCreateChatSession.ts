import { useMutation, useQueryClient } from '@tanstack/react-query'
import { startChatSession } from '@/features/agents/api'
import { queryKeys } from '@/lib/queryKeys'

/** Starts a session with its first message. */
export function useCreateChatSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: startChatSession,
    onSuccess: (session) => {
      queryClient.setQueryData(queryKeys.chatSession(session.id), session)
      return queryClient.invalidateQueries({ queryKey: queryKeys.chatSessions, exact: true })
    },
  })
}
