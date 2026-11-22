import { useQuery } from '@tanstack/react-query'
import { getChatSession } from '@/features/agents/api'
import { queryKeys } from '@/lib/queryKeys'

/** The session with its messages. The data is null when the session does not exist. */
export function useChatSession(id: number) {
  return useQuery({ queryKey: queryKeys.chatSession(id), queryFn: () => getChatSession(id) })
}
