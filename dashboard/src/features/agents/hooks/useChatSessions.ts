import { useQuery } from '@tanstack/react-query'
import { listChatSessions } from '@/features/agents/api'
import { queryKeys } from '@/lib/queryKeys'

export function useChatSessions() {
  return useQuery({ queryKey: queryKeys.chatSessions, queryFn: listChatSessions })
}
