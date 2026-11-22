import { Link, useParams } from '@tanstack/react-router'
import { CircleAlert, MessageSquareOff } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { ChatPanel } from '@/features/agents/components/ChatPanel'
import { useChatSession } from '@/features/agents/hooks/useChatSession'
import { useDecideToolCall } from '@/features/agents/hooks/useDecideToolCall'
import { useReplyStream } from '@/features/agents/hooks/useReplyStream'
import { useRetryReply } from '@/features/agents/hooks/useRetryReply'
import { useSendChatMessage } from '@/features/agents/hooks/useSendChatMessage'

/** /agents/$sessionId: a saved session. */
export function SessionChat() {
  const { sessionId } = useParams({ from: '/signed-in/agents/$sessionId' })
  // A new key per session, so the draft and a pending send never carry over to another session.
  return <Session key={sessionId} id={sessionId} />
}

function Session({ id }: { id: number }) {
  const session = useChatSession(id)
  const send = useSendChatMessage(id)
  const { reply } = useReplyStream(id)
  const retry = useRetryReply(id)
  const decide = useDecideToolCall(id)
  if (session.isPending) return <SessionSkeleton />
  if (session.isError) {
    return (
      <div className="mx-auto w-full max-w-[720px] px-4 py-6 sm:px-6">
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>The chat did not load</AlertTitle>
          <AlertDescription>
            {session.error.message}
            <Button variant="secondary" size="sm" className="mt-2" onClick={() => session.refetch()}>
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      </div>
    )
  }
  if (session.data === null) return <SessionNotFound />
  return (
    <ChatPanel
      messages={session.data.messages}
      sending={send.isPending ? send.variables : null}
      error={send.error?.message ?? null}
      onSend={(content, options) => send.mutate(content, options)}
      reply={reply}
      retry={{ run: () => retry.mutate(), pending: retry.isPending, error: retry.error?.message ?? null }}
      decision={
        decide.variables && (decide.isPending || decide.isError)
          ? { ...decide.variables, pending: decide.isPending, error: decide.error?.message ?? null }
          : null
      }
      onDecide={(callId, approve) => decide.mutate({ callId, approve })}
    />
  )
}

function SessionNotFound() {
  return (
    <Empty className="flex-1 pb-16">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <MessageSquareOff aria-hidden="true" />
        </EmptyMedia>
        <EmptyTitle>Chat not found</EmptyTitle>
        <EmptyDescription>It was deleted, or it belongs to another account.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button nativeButton={false} render={<Link to="/agents" />}>
          New chat
        </Button>
      </EmptyContent>
    </Empty>
  )
}

function SessionSkeleton() {
  return (
    <div aria-busy="true" className="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-4 py-6 sm:px-6">
      <span className="sr-only">Loading the chat</span>
      <Skeleton className="h-9 w-48 self-end rounded-xl" />
      <div className="flex gap-3">
        <Skeleton className="size-6 shrink-0 rounded-full" />
        <div className="flex flex-1 flex-col gap-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      </div>
    </div>
  )
}
