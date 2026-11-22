import { ArrowUp, MessageSquare } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useAgentChat } from '@/features/agents/hooks/useAgentChat'

export function AgentChat() {
  const chat = useAgentChat()
  const [draft, setDraft] = useState('')
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end' })
  }, [chat.messages.length, chat.pending, chat.error])

  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    const content = draft.trim()
    if (!content || chat.pending) return
    chat.send(content)
    setDraft('')
  }

  // Enter sends, Shift+Enter starts a new line. Skip while an input method is composing a character.
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) submit(event)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 overflow-y-auto" aria-live="polite">
        {chat.messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center p-6 pb-16 text-center">
            <span className="flex size-10 items-center justify-center rounded-lg border bg-card shadow-[var(--highlight)]">
              <MessageSquare aria-hidden="true" className="size-5 text-muted-foreground" />
            </span>
            <h2 className="mt-4 text-xl font-semibold tracking-[-0.012em]">Chat with a model</h2>
            <p className="mt-2 max-w-[440px] text-balance text-muted-foreground">
              Messages go to OpenRouter. Set OPENROUTER_API_KEY in .env and restart the backend to get replies.
            </p>
          </div>
        ) : (
          <ol className="mx-auto flex w-full max-w-[720px] flex-col gap-4 p-4 sm:p-6">
            {chat.messages.map((message, index) => (
              <li
                key={index}
                className={
                  message.role === 'user'
                    ? 'max-w-[85%] self-end rounded-xl border bg-card px-3 py-2 whitespace-pre-wrap shadow-[var(--highlight)]'
                    : 'max-w-full self-start whitespace-pre-wrap text-[var(--text-2)]'
                }
              >
                <span className="sr-only">{message.role === 'user' ? 'You: ' : 'Model: '}</span>
                {message.content}
              </li>
            ))}
            {chat.pending && <li className="self-start text-sm text-muted-foreground">Waiting for the model…</li>}
            {chat.error && (
              <li
                role="alert"
                className="self-stretch rounded-xl border border-[color-mix(in_srgb,var(--danger)_40%,transparent)] bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] px-3 py-2 text-sm text-[var(--danger-text)]"
              >
                {chat.error}
              </li>
            )}
          </ol>
        )}
        <div ref={end} />
      </div>
      <form onSubmit={submit} className="mx-auto flex w-full max-w-[720px] items-end gap-2 p-4 pt-2 sm:px-6">
        <Textarea
          aria-label="Message"
          placeholder="Send a message"
          rows={1}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          className="max-h-48 min-h-10"
        />
        {chat.messages.length > 0 && (
          <Button type="button" variant="secondary" onClick={chat.clear} disabled={chat.pending}>
            Clear
          </Button>
        )}
        <Button type="submit" size="icon-lg" aria-label="Send" disabled={!draft.trim() || chat.pending}>
          <ArrowUp aria-hidden="true" />
        </Button>
      </form>
    </div>
  )
}
