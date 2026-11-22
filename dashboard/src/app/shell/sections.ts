import { Activity, BookOpen, Bot, Plug, Wrench, type LucideIcon } from 'lucide-react'

// The sidebar lists these in order. Each path needs a route in src/app/router.tsx: the sidebar links to it,
// so a path without a route fails the typecheck. A section whose feature is not built yet has the text of its
// empty state in `empty`. A built section drops it.
type SectionShape = { path: `/${string}`; label: string; icon: LucideIcon; empty?: { title: string; body: string } }

export const sections = [
  {
    path: '/agents',
    label: 'Agents',
    icon: Bot,
  },
  {
    path: '/runs',
    label: 'Runs',
    icon: Activity,
    empty: { title: 'No runs yet', body: 'Following each run step by step, with its tool calls and token use, arrives with the next releases.' },
  },
  {
    path: '/tools',
    label: 'Tools',
    icon: Wrench,
    empty: { title: 'No tools yet', body: 'Adding the tools and MCP servers that agents can call arrives with the next releases.' },
  },
  {
    path: '/knowledge',
    label: 'Knowledge',
    icon: BookOpen,
    empty: { title: 'No knowledge yet', body: 'Uploading documents that agents can search arrives with the next releases.' },
  },
  {
    path: '/integrations',
    label: 'Integrations',
    icon: Plug,
  },
] as const satisfies readonly SectionShape[]

export type Section = (typeof sections)[number]

/** A section whose screen is still its empty state. */
export type PlannedSection = Extract<Section, { empty: object }>

/** The section of the current screen: the one whose route matched. Undefined on the not-found page. */
export const matchedSection = (matches: readonly { fullPath: string }[]) =>
  sections.find((section) => matches.some((match) => match.fullPath === section.path))
