import { ArrowUp, Bot, CircleAlert, MessageSquare, SquarePen } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty'
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupText, InputGroupTextarea } from '@/components/ui/input-group'
import { Kbd, KbdGroup } from '@/components/ui/kbd'
import { Spinner } from '@/components/ui/spinner'
import type { ChatMessage } from '@/features/agents/api'
import { useAgentChat } from '@/features/agents/hooks/useAgentChat'

const suggestions = ['What can an agent do?', 'Explain tool calls in two sentences', 'Write a system prompt for a support agent']

function ModelAvatar() {
  return (
    <Avatar size="sm" className="mt-0.5">
      <AvatarFallback className="bg-card">
        <Bot aria-hidden="true" className="size-3.5" />
      </AvatarFallback>
    </Avatar>
  )
}

function Message({ message }: { message: ChatMessage }) {
  if (message.role === 'user') {
    return (
      <li className="max-w-[85%] self-end rounded-xl bg-muted px-3.5 py-2 whitespace-pre-wrap text-foreground">
        <span className="sr-only">You: </span>
        {message.content}
      </li>
    )
  }
  return (
    <li className="flex gap-3">
      <ModelAvatar />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-muted-foreground">Model</p>
        <div className="mt-1 whitespace-pre-wrap text-[var(--text-2)]">{message.content}</div>
      </div>
    </li>
  )
}

export function AgentChat() {
  const chat = useAgentChat()
  const [draft, setDraft] = useState('')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [chat.messages.length, chat.pending, chat.error])

  const send = (content: string) => {
    if (!content.trim() || chat.pending) return
    chat.send(content.trim())
    setDraft('')
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

  const started = chat.messages.length > 0

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto">
        {started ? (
          <ol aria-live="polite" className="mx-auto flex w-full max-w-[720px] flex-col gap-6 px-4 py-6 sm:px-6">
            {chat.messages.map((message, index) => (
              <Message key={index} message={message} />
            ))}
            {chat.pending && (
              <li className="flex items-center gap-3 text-sm text-muted-foreground">
                <ModelAvatar />
                <Spinner aria-hidden="true" />
                Waiting for the model
              </li>
            )}
            {chat.error && (
              <li>
                <Alert variant="destructive">
                  <CircleAlert aria-hidden="true" />
                  <AlertTitle>The model did not reply</AlertTitle>
                  <AlertDescription>{chat.error}</AlertDescription>
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
                Messages go to OpenRouter through the backend. Replies need{' '}
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
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={onKeyDown}
            className="max-h-48 min-h-12 px-3.5 pt-3"
          />
          <InputGroupAddon align="block-end" className="gap-1 px-2">
            {started && (
              <InputGroupButton onClick={chat.clear} disabled={chat.pending} className="text-muted-foreground">
                <SquarePen aria-hidden="true" />
                New chat
              </InputGroupButton>
            )}
            <InputGroupText className="ml-auto hidden gap-1 text-xs sm:flex">
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
              disabled={!draft.trim() || chat.pending}
              className="ml-auto rounded-full sm:ml-2"
            >
              <ArrowUp aria-hidden="true" />
            </InputGroupButton>
          </InputGroupAddon>
        </InputGroup>
      </form>
    </div>
  )
}
