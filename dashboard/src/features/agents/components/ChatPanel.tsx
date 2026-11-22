import { ArrowUp, Bot, CircleAlert, MessageSquare } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupText, InputGroupTextarea } from '@/components/ui/input-group'
import { Kbd, KbdGroup } from '@/components/ui/kbd'
import { Spinner } from '@/components/ui/spinner'
import type { ChatMessage, ReplyState } from '@/features/agents/api'
import { ToolCallCard } from '@/features/agents/components/ToolCallCard'

const suggestions = ['What can an agent do?', 'Explain tool calls in two sentences', 'Write a system prompt for a support agent']

// Each chat screen mounts its own composer. Focus it with a mouse or trackpad, but not on a phone, where focus opens
// the keyboard over the chat.
const focusComposer = window.matchMedia('(pointer: fine)').matches

/** The decision on a tool call that is being saved, or the error that stopped it. */
export type DecisionState = { callId: number; approve: boolean; pending: boolean; error: string | null }

type Props = {
  messages: ChatMessage[]
  /** The message on its way, shown until the server saved it. */
  sending: string | null
  /** Why the server refused the last message. Nothing of it was saved. */
  error: string | null
  /** Sends a message. When the server refuses it, the panel puts the message back in the composer. */
  onSend: (content: string, options: { onError: () => void }) => void
  /** The model's reply while it streams, or why it stopped. */
  reply?: ReplyState
  /** Asks the model again when the conversation has no answer, such as after a reply that failed. */
  retry?: { run: () => void; pending: boolean; error: string | null }
  decision?: DecisionState | null
  onDecide?: (callId: number, approve: boolean) => void
}

function ModelAvatar() {
  return (
    <Avatar size="sm" className="mt-0.5">
      <AvatarFallback className="bg-card">
        <Bot aria-hidden="true" className="size-3.5" />
      </AvatarFallback>
    </Avatar>
  )
}

function UserMessage({ content }: { content: string }) {
  return (
    <li className="max-w-[85%] self-end rounded-xl bg-muted px-3.5 py-2 whitespace-pre-wrap text-foreground">
      <span className="sr-only">You: </span>
      {content}
    </li>
  )
}

type MessageProps = {
  message: ChatMessage
  decision: DecisionState | null
  onDecide: ((callId: number, approve: boolean) => void) | null
}

function Message({ message, decision, onDecide }: MessageProps) {
  if (message.role === 'user') return <UserMessage content={message.content} />
  return (
    <li className="flex gap-3">
      <ModelAvatar />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-muted-foreground">{message.model}</p>
        {message.content && <div className="mt-1 whitespace-pre-wrap text-[var(--text-2)]">{message.content}</div>}
        {message.toolCalls.map((call) => (
          <ToolCallCard
            key={call.id}
            call={call}
            decision={decision?.callId === call.id ? decision : null}
            onDecide={onDecide && ((approve) => onDecide(call.id, approve))}
          />
        ))}
      </div>
    </li>
  )
}

function Waiting() {
  return (
    <li className="flex items-center gap-3 text-sm text-muted-foreground">
      <ModelAvatar />
      <Spinner aria-hidden="true" />
      Waiting for the model
    </li>
  )
}

function StreamingReply({ text }: { text: string }) {
  return (
    <li className="flex gap-3">
      <ModelAvatar />
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
          <Spinner aria-hidden="true" className="size-3.5" />
          Replying
        </p>
        <div className="mt-1 whitespace-pre-wrap text-[var(--text-2)]">{text}</div>
      </div>
    </li>
  )
}

/** Whether the conversation ends without the model's answer: after the user's message, or after decided tool calls. */
function unanswered(messages: ChatMessage[]) {
  const last = messages.at(-1)
  return last !== undefined && (last.role === 'user' || last.toolCalls.length > 0)
}

export function ChatPanel({ messages, sending, error, onSend, reply, retry, decision = null, onDecide }: Props) {
  const [draft, setDraft] = useState('')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [messages, sending, error, reply])

  const streaming = reply?.phase === 'streaming'
  const awaitingDecision = messages.some((m) => m.role === 'assistant' && m.toolCalls.some((c) => c.outcome.status === 'pending'))
  const busy = sending !== null || streaming || !!retry?.pending || !!decision?.pending
  const showRetry = retry && !streaming && sending === null && !decision?.pending && !awaitingDecision && unanswered(messages)

  const send = (text: string) => {
    const content = text.trim()
    if (!content || busy || awaitingDecision) return
    setDraft('')
    // Keep anything typed while the message was on its way.
    onSend(content, { onError: () => setDraft((current) => current || content) })
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    send(draft)
  }

  // Enter sends, Shift+Enter starts a new line. Skip while an input method is composing a character.
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      send(draft)
    }
  }

  const started = messages.length > 0 || sending !== null || error !== null

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto">
        {started ? (
          <ol
            aria-live="polite"
            aria-busy={streaming}
            className="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-4 py-6 sm:px-6"
          >
            {messages.map((message) => (
              <Message
                key={message.id}
                message={message}
                decision={decision}
                onDecide={onDecide && !busy ? onDecide : null}
              />
            ))}
            {sending !== null && (
              <>
                <UserMessage content={sending} />
                <Waiting />
              </>
            )}
            {streaming && (reply.text ? <StreamingReply text={reply.text} /> : <Waiting />)}
            {error !== null && (
              <li>
                <Alert variant="destructive">
                  <CircleAlert aria-hidden="true" />
                  <AlertTitle>The model did not reply</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              </li>
            )}
            {showRetry && (
              <li>
                <Alert variant="destructive">
                  <CircleAlert aria-hidden="true" />
                  <AlertTitle>The model did not reply</AlertTitle>
                  <AlertDescription>
                    <p>{retry.error ?? (reply?.phase === 'failed' ? reply.error : 'The reply stopped before it finished.')}</p>
                    <Button variant="secondary" size="sm" className="mt-2" disabled={retry.pending} onClick={retry.run}>
                      {retry.pending && <Spinner aria-hidden="true" />}
                      Try again
                    </Button>
                  </AlertDescription>
                </Alert>
              </li>
            )}
          </ol>
        ) : (
          <Empty className="h-full pb-16">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <MessageSquare aria-hidden="true" />
              </EmptyMedia>
              <EmptyTitle>Chat with a model</EmptyTitle>
              <EmptyDescription>
                Messages go to OpenRouter through the backend, and each chat is saved to your account. Replies need{' '}
                <code className="font-mono text-[13px] text-foreground">OPENROUTER_API_KEY</code> in{' '}
                <code className="font-mono text-[13px] text-foreground">.env</code>.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent className="max-w-xl flex-row flex-wrap justify-center">
              {suggestions.map((suggestion) => (
                <Button key={suggestion} variant="secondary" size="sm" onClick={() => send(suggestion)}>
                  {suggestion}
                </Button>
              ))}
            </EmptyContent>
          </Empty>
        )}
        <div ref={end} />
      </div>
      <form onSubmit={submit} className="mx-auto w-full max-w-[720px] px-4 pb-4 sm:px-6">
        <InputGroup className="rounded-xl shadow-[var(--highlight)]">
          <InputGroupTextarea
            aria-label="Message"
            placeholder={awaitingDecision ? 'Approve or decline the event first' : 'Send a message'}
            disabled={awaitingDecision}
            rows={1}
            autoFocus={focusComposer}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            className="max-h-48 min-h-12 px-3.5 pt-3"
          />
          <InputGroupAddon align="block-end" className="gap-1 px-2">
            {!awaitingDecision && (
              <InputGroupText className="hidden gap-1 text-xs sm:flex">
                <Kbd>Enter</Kbd> to send
                <span aria-hidden="true" className="px-1">·</span>
                <KbdGroup>
                  <Kbd>Shift</Kbd>
                  <Kbd>Enter</Kbd>
                </KbdGroup>{' '}
                new line
              </InputGroupText>
            )}
            <InputGroupButton
              type="submit"
              variant="default"
              size="icon-sm"
              aria-label="Send"
              disabled={!draft.trim() || busy || awaitingDecision}
              className="ml-auto rounded-full"
            >
              <ArrowUp aria-hidden="true" />
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
      </form>
    </div>
  )
}
