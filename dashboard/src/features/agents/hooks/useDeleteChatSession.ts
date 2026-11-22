import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteChatSession, type ChatSessionSummary } from '@/features/agents/api'
import { queryKeys } from '@/lib/queryKeys'

export function useDeleteChatSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteChatSession,
    onSuccess: (_, id) => {
      queryClient.setQueryData<ChatSessionSummary[]>(queryKeys.chatSessions, (sessions) => sessions?.filter((s) => s.id !== id))
      // Null, as a fetch would now answer, rather than removing the query: a screen still showing it would refetch.
      queryClient.setQueryData(queryKeys.chatSession(id), null)
    },
  })
}
