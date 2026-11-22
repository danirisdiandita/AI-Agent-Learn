import { CalendarPlus, CircleAlert, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import type { CalendarEvent, ToolCall, ToolCallOutcome } from '@/features/agents/api'

const TITLES: Record<string, string> = { create_calendar_event: 'Create calendar event' }

const browserTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone

// The event's start and end are the clock times in its own zone. Read as UTC and formatted in UTC, they show exactly
// that clock, with no conversion to the browser's zone.
const eventTime = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  timeZone: 'UTC',
})

function wallClock(value: string) {
  const [date, time] = value.split('T')
  const [year, month, day] = date.split('-').map(Number)
  const [hour, minute, second = 0] = time.split(':').map(Number)
  return new Date(Date.UTC(year, month - 1, day, hour, minute, second))
}

function formatWhen(event: CalendarEvent) {
  const range = eventTime.formatRange(wallClock(event.start), wallClock(event.end))
  return event.timeZone === browserTimeZone ? range : `${range} (${event.timeZone.replaceAll('_', ' ')})`
}

type Decision = { approve: boolean; pending: boolean; error: string | null }

type Props = {
  call: ToolCall
  /** The user's decision on this call while it is saved, or the error that stopped it. */
  decision: Decision | null
  /** Approves or declines the call. Missing while another request in the chat is under way. */
  onDecide: ((approve: boolean) => void) | null
}

/** A tool call in the chat: what the model wants to do, and Approve and Decline while it waits for the user. */
export function ToolCallCard({ call, decision, onDecide }: Props) {
  const title = TITLES[call.name] ?? call.name
  const { event, outcome } = call
  return (
    <div role="group" aria-label={title} className="mt-3 rounded-xl border bg-card p-4 shadow-[var(--highlight)]">
      <p className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <CalendarPlus aria-hidden="true" className="size-4" />
        {title}
      </p>
      {event ? (
        <>
          <p className="mt-2 text-[length:var(--font-h3)] leading-[1.3] font-[560] tracking-[-0.012em] break-words text-foreground">
            {event.summary}
          </p>
          <p className="mt-1 text-sm text-[var(--text-2)]">{formatWhen(event)}</p>
          {event.description && (
            <p className="mt-3 text-sm whitespace-pre-wrap text-muted-foreground">{event.description}</p>
          )}
        </>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">The model sent an event this chat cannot show.</p>
      )}
      {outcome.status === 'pending' ? (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button disabled={!onDecide || decision?.pending} onClick={() => onDecide?.(true)}>
            {decision?.pending && decision.approve && <Spinner aria-hidden="true" />}
            Approve
          </Button>
          <Button variant="secondary" disabled={!onDecide || decision?.pending} onClick={() => onDecide?.(false)}>
            {decision?.pending && !decision.approve && <Spinner aria-hidden="true" />}
            Decline
          </Button>
          {decision?.error && (
            <p role="alert" className="flex basis-full items-center gap-1.5 text-sm text-[var(--danger-text)]">
              <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
              {decision.error}
            </p>
          )}
        </div>
      ) : (
        <Outcome outcome={outcome} />
      )}
    </div>
  )
}

const STATES = {
  approved: { label: 'Approved, but the result was not saved', dot: 'bg-[var(--warning)]' },
  declined: { label: 'Declined', dot: 'bg-[var(--text-4)]' },
  succeeded: { label: 'Created', dot: 'bg-[var(--success)]' },
  failed: { label: 'Failed', dot: 'bg-[var(--danger)]' },
}

function Outcome({ outcome }: { outcome: Exclude<ToolCallOutcome, { status: 'pending' }> }) {
  const state = STATES[outcome.status]
  return (
    <div className="mt-4 text-sm">
      <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="flex items-center gap-2 font-medium text-foreground">
          <span aria-hidden="true" className={`dot ${state.dot}`} />
          {state.label}
        </span>
        {outcome.status === 'succeeded' && outcome.link && (
          <a
            href={outcome.link}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 font-medium text-brand underline-offset-3 hover:underline"
          >
            Open in Google Calendar
            <ExternalLink aria-hidden="true" className="size-3.5" />
          </a>
        )}
      </p>
      {outcome.status === 'failed' && <p className="mt-1 text-[var(--danger-text)]">{outcome.error}</p>}
    </div>
  )
}
