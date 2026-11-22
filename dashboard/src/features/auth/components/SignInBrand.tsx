import { Boxes, Code, Server, type LucideIcon } from 'lucide-react'

type Point = readonly [number, number]

// One branch of a run: the steps an agent took for one task, in order. Steps before `done` have finished.
type Branch = { color: string; steps: Point[]; done: number }

const AGENT: Point = [300, 200]

const branches: Branch[] = [
  { color: 'var(--series-1)', steps: [[240, 150], [180, 116], [118, 138], [96, 198], [150, 244], [228, 232]], done: 4 },
  { color: 'var(--series-2)', steps: [[342, 138], [398, 88], [470, 78], [522, 128], [482, 172], [384, 182]], done: 3 },
  { color: 'var(--series-3)', steps: [[372, 242], [452, 262], [532, 292], [502, 342], [420, 332], [342, 292]], done: 2 },
  { color: 'var(--series-4)', steps: [[262, 272], [202, 312], [122, 322], [88, 282], [170, 280], [250, 250]], done: 5 },
]

const values: { Icon: LucideIcon; title: string; body: string }[] = [
  { Icon: Server, title: 'Self-hosted', body: 'Run it on your own servers. Your prompts and data never leave them.' },
  { Icon: Boxes, title: 'Any model', body: 'Bring your own model provider and keys. Switch models per agent.' },
  { Icon: Code, title: 'Open source', body: 'Read the code, change the agent loop, and send improvements back.' },
]

const branchPath = (steps: Point[]) => [AGENT, ...steps, AGENT].map(([x, y]) => `${x},${y}`).join(' ')

// The graph is scaled to fit inside the frame, so every route stays in view. The background and grid
// reach far past the 620x400 view box to fill whatever space the frame has left around it.
const BLEED = 1000
const gridLines = Array.from({ length: 66 }, (_, i) => 20 - BLEED + i * 40)

function RunGraph() {
  return (
    <svg className="absolute inset-0 size-full" viewBox="0 0 620 400" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <rect x={-BLEED} y={-BLEED} width={620 + 2 * BLEED} height={400 + 2 * BLEED} style={{ fill: 'var(--surface-inset)' }} />
      <g style={{ stroke: 'color-mix(in srgb, var(--text) 5.5%, transparent)' }} strokeWidth="1">
        {gridLines.map((n) => (
          <g key={n}>
            <line x1={n} y1={-BLEED} x2={n} y2={400 + BLEED} />
            <line x1={-BLEED} y1={n} x2={620 + BLEED} y2={n} />
          </g>
        ))}
      </g>
      {branches.map((r) => (
        <polyline
          key={r.color}
          points={branchPath(r.steps)}
          fill="none"
          style={{ stroke: r.color }}
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          opacity="0.9"
        />
      ))}
      {branches.map((r) =>
        r.steps.map(([x, y], i) => (
          <circle
            key={`${r.color}${i}`}
            cx={x}
            cy={y}
            r="5"
            strokeWidth="2"
            style={{ fill: i < r.done ? r.color : 'var(--surface-inset)', stroke: i < r.done ? 'var(--surface-inset)' : r.color }}
          />
        )),
      )}
      {branches.map((r) => {
        const [x, y] = r.steps[r.done]
        return (
          <g key={`live${r.color}`}>
            <circle
              className="origin-center opacity-35 [transform-box:fill-box] motion-safe:animate-ping"
              cx={x}
              cy={y}
              r="9"
              style={{ fill: r.color }}
            />
            <circle cx={x} cy={y} r="6.5" strokeWidth="2" style={{ fill: r.color, stroke: 'var(--text)' }} />
          </g>
        )
      })}
      <rect x={AGENT[0] - 8} y={AGENT[1] - 8} width="16" height="16" rx="3" style={{ fill: 'var(--text)' }} />
    </svg>
  )
}

export function SignInBrand() {
  return (
    <aside className="relative hidden flex-col gap-10 overflow-hidden border-l border-border bg-[var(--bg-raised)] p-12 lg:flex">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 -top-[200px] h-[900px] bg-[radial-gradient(ellipse_60%_40%_at_50%_20%,var(--accent-soft),transparent_70%),radial-gradient(ellipse_40%_30%_at_80%_45%,color-mix(in_srgb,var(--series-4)_8%,transparent),transparent_70%)]"
      />
      <div className="relative flex items-center gap-2.5 text-[length:var(--font-body)] font-semibold tracking-[-0.01em] text-foreground">
        <img src="/favicon.svg" width={24} height={24} alt="" />
        Nextsci
      </div>
      <div className="relative max-w-[560px]">
        <p className="mb-4 text-[length:var(--font-small)] font-[560] text-brand">Open-source AI agents</p>
        <h2 className="bg-[linear-gradient(180deg,var(--text)_30%,color-mix(in_srgb,var(--text)_55%,transparent))] bg-clip-text text-[length:var(--font-h2)] leading-[1.08] font-semibold tracking-[-0.03em] text-transparent">
          Build AI agents you can watch think
        </h2>
        <p className="mt-5 text-[length:var(--font-body)] text-[var(--text-3)]">
          Give an agent a model, instructions, and tools, then follow every step of each run.
        </p>
      </div>
      <div className="relative min-h-[180px] flex-1 overflow-hidden rounded-2xl border border-border">
        <RunGraph />
      </div>
      <ul className="relative grid grid-cols-3 gap-6">
        {values.map(({ Icon, title, body }) => (
          <li key={title} className="flex flex-col gap-1.5">
            <Icon className="size-4 text-[var(--text-3)]" aria-hidden="true" />
            <span className="mt-1 text-[length:var(--font-small)] font-[560] text-foreground">{title}</span>
            <span className="text-[length:var(--font-small)] font-normal text-[var(--text-3)]">{body}</span>
          </li>
        ))}
      </ul>
    </aside>
  )
}
