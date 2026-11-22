import { Link, useNavigate } from '@tanstack/react-router'
import { SquarePen, Trash2 } from 'lucide-react'
import { useState } from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import type { ChatSessionSummary } from '@/features/agents/api'
import { useChatSessions } from '@/features/agents/hooks/useChatSessions'
import { useDeleteChatSession } from '@/features/agents/hooks/useDeleteChatSession'

const relative = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })
const units = [
  ['year', 365 * 86400],
  ['month', 30 * 86400],
  ['week', 7 * 86400],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
] as const

/** How long ago a date was, such as "5 minutes ago" or "yesterday". */
function ago(date: Date) {
  const seconds = (date.getTime() - Date.now()) / 1000
  const unit = units.find(([, size]) => Math.abs(seconds) >= size)
  return unit ? relative.format(Math.round(seconds / unit[1]), unit[0]) : 'just now'
}

type Props = {
  /** The session on screen, if any. */
  activeId: number | undefined
  /** Called when a link in the list is followed, so the phone sheet can close. */
  onNavigate?: () => void
}

export function ChatSessionList({ activeId, onNavigate }: Props) {
  const sessions = useChatSessions()
  // The session to delete stays set while the dialog closes, so its text does not vanish during the fade.
  const [target, setTarget] = useState<{ session: ChatSessionSummary; open: boolean } | null>(null)
  return (
    <nav aria-label="Chats" className="flex min-h-0 flex-1 flex-col">
      <div className="p-3">
        <Button
          variant="secondary"
          className="w-full justify-start"
          nativeButton={false}
          render={<Link to="/agents" activeOptions={{ exact: true }} onClick={onNavigate} />}
        >
          <SquarePen aria-hidden="true" />
          New chat
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {sessions.isPending ? (
          <ListSkeleton />
        ) : sessions.isError ? (
          <div role="alert" className="flex flex-col items-start gap-2 px-2.5 py-2 text-sm text-[var(--danger-text)]">
            {sessions.error.message}
            <Button variant="secondary" size="sm" onClick={() => sessions.refetch()}>
              Try again
            </Button>
          </div>
        ) : sessions.data.length === 0 ? (
          <p className="px-2.5 py-2 text-sm text-muted-foreground">Your chats appear here.</p>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {sessions.data.map((session) => (
              <li key={session.id} className="group/chat relative">
                <Link
                  to="/agents/$sessionId"
                  params={{ sessionId: session.id }}
                  onClick={onNavigate}
                  className="flex flex-col gap-0.5 rounded-md py-2 pr-10 pl-2.5 text-[var(--text-2)] outline-none hover:bg-sidebar-accent/60 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring aria-[current=page]:bg-sidebar-accent aria-[current=page]:text-foreground aria-[current=page]:shadow-[var(--highlight)]"
                >
                  <span className="truncate text-sm font-medium">{session.title}</span>
                  <time
                    dateTime={session.updatedAt.toISOString()}
                    title={session.updatedAt.toLocaleString()}
                    className="text-xs text-muted-foreground"
                  >
                    {ago(session.updatedAt)}
                  </time>
                </Link>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Delete ${session.title}`}
                  onClick={() => setTarget({ session, open: true })}
                  // Shown on hover or keyboard focus with a mouse, always on a touch screen.
                  className="absolute top-1/2 right-1.5 -translate-y-1/2 text-muted-foreground opacity-0 group-hover/chat:opacity-100 focus-visible:opacity-100 pointer-coarse:opacity-100"
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <DeleteDialog
        session={target?.session ?? null}
        open={target?.open ?? false}
        activeId={activeId}
        onClose={() => setTarget((current) => current && { ...current, open: false })}
        onClosed={() => setTarget(null)}
      />
    </nav>
  )
}

type DeleteDialogProps = {
  session: ChatSessionSummary | null
  open: boolean
  activeId: number | undefined
  onClose: () => void
  onClosed: () => void
}

function DeleteDialog({ session, open, activeId, onClose, onClosed }: DeleteDialogProps) {
  const remove = useDeleteChatSession()
  const navigate = useNavigate()
  const close = () => {
    remove.reset()
    onClose()
  }
  const confirm = () => {
    if (!session) return
    remove.mutate(session.id, {
      onSuccess: () => {
        close()
        if (session.id === activeId) void navigate({ to: '/agents', replace: true })
      },
    })
  }
  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => !next && !remove.isPending && close()}
      onOpenChangeComplete={(next) => !next && onClosed()}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this chat?</AlertDialogTitle>
          <AlertDialogDescription>
            {session && `“${session.title}” and all its messages will be deleted. This cannot be undone.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        {remove.error && (
          <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-[var(--danger-text)]">
            {remove.error.message}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={remove.isPending}>Cancel</AlertDialogCancel>
          <AlertDialogAction variant="destructive" disabled={remove.isPending} onClick={confirm}>
            {remove.isPending ? 'Deleting…' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

function ListSkeleton() {
  return (
    <div aria-busy="true" className="flex flex-col gap-1">
      <span className="sr-only">Loading your chats</span>
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex flex-col gap-1.5 px-2.5 py-2">
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      ))}
    </div>
  )
}
