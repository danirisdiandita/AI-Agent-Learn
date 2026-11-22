import { Link, Outlet, useParams } from '@tanstack/react-router'
import { History, SquarePen } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { ChatSessionList } from '@/features/agents/components/ChatSessionList'
import { useChatSessions } from '@/features/agents/hooks/useChatSessions'

/**
 * The Agents screen: the list of chats beside the open chat. The list stays mounted while the chat beside it changes.
 * Under 1024px the list moves into a sheet that a toolbar above the chat opens.
 */
export function AgentsPage() {
  const { sessionId } = useParams({ strict: false })
  return (
    // The screen fills the window under the 56px shell header, so the list and the chat each scroll on their own.
    <div className="flex h-[calc(100dvh-56px)] min-h-0">
      <aside className="hidden w-64 shrink-0 flex-col border-r lg:flex">
        <ChatSessionList activeId={sessionId} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <PhoneToolbar activeId={sessionId} />
        <Outlet />
      </div>
    </div>
  )
}

function PhoneToolbar({ activeId }: { activeId: number | undefined }) {
  const [open, setOpen] = useState(false)
  const sessions = useChatSessions()
  const title = activeId === undefined ? 'New chat' : (sessions.data?.find((s) => s.id === activeId)?.title ?? '')
  return (
    <div className="flex h-12 shrink-0 items-center gap-2 border-b px-2 lg:hidden">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger render={<Button variant="ghost" size="sm" className="text-muted-foreground" />}>
          <History aria-hidden="true" />
          Chats
        </SheetTrigger>
        <SheetContent side="left" className="w-72 gap-0 p-0">
          <SheetHeader className="h-12 justify-center border-b px-4 py-0">
            <SheetTitle>Chats</SheetTitle>
          </SheetHeader>
          <ChatSessionList activeId={activeId} onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
      <h2 className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{title}</h2>
      <Button variant="ghost" size="icon-sm" aria-label="New chat" nativeButton={false} render={<Link to="/agents" />}>
        <SquarePen aria-hidden="true" />
      </Button>
    </div>
  )
}
