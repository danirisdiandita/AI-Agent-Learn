import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from '@tanstack/react-router'
import { useState } from 'react'
import { sendChat, Unauthorized, type ChatMessage } from '@/features/agents/api'
import { queryKeys } from '@/lib/queryKeys'

/** The conversation on the Agents screen. It lives only as long as the screen. */
export function useAgentChat() {
  const queryClient = useQueryClient()
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])

  const send = async (conversation: ChatMessage[]) => {
    try {
      return await sendChat(conversation)
    } catch (error) {
      if (error instanceof Unauthorized) {
        // authedFetch already tried to refresh the token, so the refresh token expired too. Dropping the
        // session reruns the route guard, which sends the user to sign-in.
        queryClient.removeQueries({ queryKey: queryKeys.session })
        await router.invalidate()
      }
      throw error
    }
  }

  const mutation = useMutation({
    mutationFn: send,
    onSuccess: (reply) => setMessages((current) => [...current, reply]),
  })

  return {
    messages,
    pending: mutation.isPending,
    error: mutation.error?.message ?? null,
    send: (content: string) => {
      const conversation = [...messages, { role: 'user' as const, content }]
      setMessages(conversation)
      mutation.mutate(conversation)
    },
    clear: () => {
      setMessages([])
      mutation.reset()
    },
  }
}
