import { Activity, BookOpen, Bot, Wrench, type LucideIcon } from 'lucide-react'

// The sidebar lists these in order. Each path needs a route in src/app/router.tsx: the sidebar links to it,
// so a path without a route fails the typecheck.
type SectionShape = { path: `/${string}`; label: string; icon: LucideIcon; empty: { title: string; body: string } }

export const sections = [
  {
    path: '/agents',
    label: 'Agents',
    icon: Bot,
    empty: { title: 'No agents yet', body: 'Defining agents with a model, instructions, and tools arrives with the next releases.' },
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
] as const satisfies readonly SectionShape[]

export type Section = (typeof sections)[number]

/** The section of the current screen: the one whose route matched. Undefined on the not-found page. */
export const matchedSection = (matches: readonly { fullPath: string }[]) =>
  sections.find((section) => matches.some((match) => match.fullPath === section.path))
