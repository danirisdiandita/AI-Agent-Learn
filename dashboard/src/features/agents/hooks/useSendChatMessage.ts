import { useMutation, useQueryClient } from '@tanstack/react-query'
import { sendChatMessage, type ChatSession } from '@/features/agents/api'
import { queryKeys } from '@/lib/queryKeys'

/** Sends a message in a session that already exists. */
export function useSendChatMessage(sessionId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (content: string) => sendChatMessage(sessionId, content),
    onSuccess: (messages) => {
      queryClient.setQueryData<ChatSession | null>(
        queryKeys.chatSession(sessionId),
        (session) => session && { ...session, messages: [...session.messages, ...messages] },
      )
      // The list orders sessions by their latest message, and takes the title from the first.
      void queryClient.invalidateQueries({ queryKey: queryKeys.chatSessions, exact: true })
    },
  })
}
