import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { ChevronsUpDown, LogOut } from 'lucide-react'
import { sections, type Section } from '@/app/shell/sections'
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar'
import type { User } from '@/features/auth/api'
import { useSignOut } from '@/features/auth/hooks/useSignOut'

// Text beside an icon fades while the sidebar narrows to its icon rail, so it never shows half clipped.
const fade = 'transition-opacity duration-200 ease-out group-data-[collapsible=icon]:opacity-0'

type Props = { user: User; active: Section | undefined }

// Every icon, the logo, and the avatar center on one vertical axis, and every label starts at the same x,
// so nothing moves sideways when the sidebar collapses.
export function AppSidebar({ user, active }: Props) {
  const { setOpenMobile } = useSidebar()
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="h-14 justify-center border-b border-sidebar-border">
        <div className="brand h-9 overflow-hidden pl-2">
          <img src="/favicon.svg" width={20} height={20} alt="" className="shrink-0" />
          <span className={fade}>Nextsci</span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu className="gap-1">
            {sections.map((section) => (
              <SidebarMenuItem key={section.path}>
                <SidebarMenuButton
                  isActive={section === active}
                  tooltip={section.label}
                  // The link would mark itself current by its path alone. The matched route decides instead, as for
                  // isActive, so /agents/<id> marks Agents current and a not-found path under /agents marks nothing.
                  render={
                    <Link
                      to={section.path}
                      activeOptions={{ exact: true, includeSearch: false }}
                      aria-current={section === active ? 'page' : undefined}
                    />
                  }
                  onClick={() => setOpenMobile(false)}
                >
                  <section.icon
                    aria-hidden="true"
                    className="text-muted-foreground group-hover/menu-button:text-foreground group-data-active/menu-button:text-foreground"
                  />
                  <span className={fade}>{section.label}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="border-t border-sidebar-border">
        <UserMenu user={user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}

function UserMenu({ user }: { user: User }) {
  const signOut = useSignOut()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const { isMobile, state } = useSidebar()
  const collapsed = state === 'collapsed' && !isMobile
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger render={<SidebarMenuButton className="gap-2 p-1.5" />}>
            <span
              aria-hidden="true"
              className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-[560] text-foreground ring-1 ring-border"
            >
              {user.email.charAt(0).toUpperCase()}
            </span>
            <span className={`min-w-0 flex-1 truncate ${fade}`}>{user.email}</span>
            <ChevronsUpDown aria-hidden="true" className={`mr-1 text-muted-foreground ${fade}`} />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side={collapsed ? 'right' : 'top'}
            align={collapsed ? 'end' : 'start'}
            sideOffset={collapsed ? 16 : 8}
            className="min-w-56"
          >
            <DropdownMenuGroup>
              <DropdownMenuLabel>Signed in as</DropdownMenuLabel>
              <p className="truncate px-1.5 pb-1.5 text-sm text-foreground">{user.email}</p>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => setConfirmOpen(true)}>
              <LogOut aria-hidden="true" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Sign out?</AlertDialogTitle>
              <AlertDialogDescription>You will need your email and password to sign back in.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={signOut}>Sign out</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
