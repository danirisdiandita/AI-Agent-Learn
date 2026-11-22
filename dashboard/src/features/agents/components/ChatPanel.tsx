import { ArrowUp, Bot, CircleAlert, MessageSquare } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupText, InputGroupTextarea } from '@/components/ui/input-group'
import { Kbd, KbdGroup } from '@/components/ui/kbd'
import { Spinner } from '@/components/ui/spinner'
import type { ChatMessage } from '@/features/agents/api'

const suggestions = ['What can an agent do?', 'Explain tool calls in two sentences', 'Write a system prompt for a support agent']

// Each chat screen mounts its own composer. Focus it with a mouse or trackpad, but not on a phone, where focus opens
// the keyboard over the chat.
const focusComposer = window.matchMedia('(pointer: fine)').matches

type Props = {
  messages: ChatMessage[]
  /** The message on its way, shown until the reply arrives. */
  pending: string | null
  error: string | null
  /** Sends a message. On failure, the panel puts the message back in the composer. */
  onSend: (content: string, options: { onError: () => void }) => void
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

function Message({ message }: { message: ChatMessage }) {
  if (message.role === 'user') return <UserMessage content={message.content} />
  return (
    <li className="flex gap-3">
      <ModelAvatar />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-muted-foreground">{message.model}</p>
        <div className="mt-1 whitespace-pre-wrap text-[var(--text-2)]">{message.content}</div>
      </div>
    </li>
  )
}

export function ChatPanel({ messages, pending, error, onSend }: Props) {
  const [draft, setDraft] = useState('')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, pending, error])

  const send = (text: string) => {
    const content = text.trim()
    if (!content || pending !== null) return
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

  const started = messages.length > 0 || pending !== null || error !== null

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto">
        {started ? (
          <ol aria-live="polite" className="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-4 py-6 sm:px-6">
            {messages.map((message) => (
              <Message key={message.id} message={message} />
            ))}
            {pending !== null && (
              <>
                <UserMessage content={pending} />
                <li className="flex items-center gap-3 text-sm text-muted-foreground">
                  <ModelAvatar />
                  <Spinner aria-hidden="true" />
                  Waiting for the model
                </li>
              </>
            )}
            {error !== null && (
              <li>
                <Alert variant="destructive">
                  <CircleAlert aria-hidden="true" />
                  <AlertTitle>The model did not reply</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
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
            placeholder="Send a message"
            rows={1}
            autoFocus={focusComposer}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            className="max-h-48 min-h-12 px-3.5 pt-3"
          />
          <InputGroupAddon align="block-end" className="gap-1 px-2">
            <InputGroupText className="hidden gap-1 text-xs sm:flex">
              <Kbd>Enter</Kbd> to send
              <span aria-hidden="true" className="px-1">·</span>
              <KbdGroup>
                <Kbd>Shift</Kbd>
                <Kbd>Enter</Kbd>
              </KbdGroup>{' '}
              new line
            </InputGroupText>
            <InputGroupButton
              type="submit"
              variant="default"
              size="icon-sm"
              aria-label="Send"
              disabled={!draft.trim() || pending !== null}
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
