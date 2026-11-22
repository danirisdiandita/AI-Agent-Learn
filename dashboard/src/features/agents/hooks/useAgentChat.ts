import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useRouter } from '@tanstack/react-router'
import { useState } from 'react'
import { accessToken, sendChat, Unauthorized, type ChatMessage } from '@/features/agents/api'
import { queryKeys } from '@/lib/queryKeys'

/** The conversation on the Agents screen. It lives only as long as the screen. */
export function useAgentChat() {
  const queryClient = useQueryClient()
  const router = useRouter()
  const [messages, setMessages] = useState<ChatMessage[]>([])

  const send = async (conversation: ChatMessage[]) => {
    const access = accessToken(queryClient.getQueryData(queryKeys.session))
    if (!access) throw new Unauthorized('Your session expired. Sign in again.')
    try {
      return await sendChat(access, conversation)
    } catch (error) {
      if (!(error instanceof Unauthorized)) throw error
      // The access token lasts 15 minutes. Dropping the session makes the route guard restore it, which
      // refreshes the token, or sends the user to sign-in when the refresh token expired too.
      queryClient.removeQueries({ queryKey: queryKeys.session })
      await router.invalidate()
      const renewed = accessToken(queryClient.getQueryData(queryKeys.session))
      if (!renewed) throw error
      return sendChat(renewed, conversation)
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
