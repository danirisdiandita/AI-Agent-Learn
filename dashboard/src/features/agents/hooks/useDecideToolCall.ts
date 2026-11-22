import { useMutation, useQueryClient } from '@tanstack/react-query'
import { decideToolCall } from '@/features/agents/api'
import { useReplyStream } from '@/features/agents/hooks/useReplyStream'
import { queryKeys } from '@/lib/queryKeys'

/**
 * Approves or declines a tool call in a session. The mutation lasts until the server saved the decision and ran an
 * approved tool. The model's follow-up then streams through useReplyStream.
 */
export function useDecideToolCall(sessionId: number) {
  const queryClient = useQueryClient()
  const { follow } = useReplyStream(sessionId)
  return useMutation({
    mutationFn: ({ callId, approve }: { callId: number; approve: boolean }) => decideToolCall(callId, approve),
    onSuccess: ({ call, events }) => void follow(sessionId, events, { type: 'tool_call', call }),
    // Another tab may have decided the call already, so show what the server has.
    onError: () => queryClient.invalidateQueries({ queryKey: queryKeys.chatSession(sessionId) }),
  })
}
