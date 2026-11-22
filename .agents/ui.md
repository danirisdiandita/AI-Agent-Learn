# UI rules for the dashboard

`dashboard/` is the app that self-hosters deploy. [`DESIGNS.md`](../DESIGNS.md) defines its visual design. This file tells you how to keep the dashboard on it.

Read `DESIGNS.md` before you change anything in `dashboard/src/`.

## Rules that a script enforces

`scripts/check-design.sh` runs inside `scripts/check.sh`. It fails when you break one of these rules:

1. **No raw colors outside `design.css`.** Hex, `rgb()`, and `hsl()` values fail, because a fixed color is right in only one theme. Use `var(--token)`, or mix one for a tint: `color-mix(in srgb, var(--text) 10%, transparent)`. SVG presentation attributes such as `stroke=` cannot read variables, so set them through `style` or a class. If no token fits, add a `light-dark()` pair to `design.css` and to the tables in `DESIGNS.md` in the same commit.
2. **App styles never restyle a shared component.** A rule that starts with a shared class, such as `.btn-primary { ... }`, belongs in `design.css` only. To place a shared component, scope it with a parent selector, such as `.topbar .brand { margin-right: auto; }`.

3. **Dashboard code never reads a shadcn theme variable.** `var(--secondary)` is undefined here, and `var(--accent)` and `var(--border)` mean something else in `design.css`. Use the mapped classes described below. Only `dashboard/src/tailwind.css` may read those names.
4. **`dashboard/src/tailwind.css` has no `:root` or `.dark` block.** shadcn's default theme block overrides the design tokens.

Run the check by itself with `./scripts/check-design.sh`.

## Dashboard components come from shadcn/ui

The dashboard builds its interface from [shadcn/ui](https://ui.shadcn.com) components on Tailwind CSS v4. Every value comes from the tokens in `design.css`, through the mapping in `src/tailwind.css`.

- **Use shadcn for every interactive control.** Before you write a dialog, popover, menu, select, combobox, tooltip, tabs, toast, checkbox, or table, add the shadcn component. It handles focus, keyboard use, and screen readers, which hand-built versions usually get wrong.
- **Add a component from `dashboard/`.** Run `npx shadcn@latest add <name>`. The code lands in `src/components/ui/` and belongs to this repository, so edit it.
- **Fit each new component to `DESIGNS.md` before you use it.** Set control heights to 36px for buttons and 40px for inputs. Set button text to weight 560. Replace any raw shadcn variable with a mapped class. `components/ui/button.tsx` and `components/ui/input.tsx` are the reference.
- **Style with the mapped classes.** `src/tailwind.css` maps shadcn names to tokens: `bg-background`, `bg-card`, `bg-popover`, `bg-inset`, `text-foreground`, `text-muted-foreground`, `border-border`, `border-input`, `bg-primary`, `bg-muted`, `text-destructive`, `ring-ring`, and `text-brand` for the accent blue. When a token has no class, use it in an arbitrary value, such as `text-[var(--text-2)]`. Never write a hex or `oklch()` color.
- **Keep the mapping in one file.** If `shadcn init` or `shadcn add` rewrites `src/tailwind.css`, restore the `@theme inline` mapping and delete any `:root` or `.dark` block it added. The design check fails until you do.
- **Rename hooks that shadcn adds.** shadcn writes hooks such as `src/hooks/use-mobile.ts`. Rename each one to its hook name, such as `useIsMobile.ts`, so `scripts/check-react.sh` passes.
- **Leave `dark:` variants to shadcn.** Tokens already switch with the theme, so your own code needs no `dark:` classes. shadcn components keep theirs: `src/tailwind.css` points the `dark` variant at the theme the page shows, so they stay correct.
- **Keep `design.css` rules inside their cascade layers.** Base rules sit in `@layer base` and shared components sit in `@layer components`, so Tailwind utilities and app styles override them. An unlayered rule in `design.css` would beat every Tailwind class.

## Rules that need your judgment

- **Build from shared components first.** Look in `src/components/ui/` and in the shadcn catalog, then in the shared components section of `design.css`. Use what exists if it is close enough.
- **Describe shared components.** When you add a component to `design.css`, describe it in `DESIGNS.md` in the same commit.
- **Keep app stylesheets small.** Layout and app-only parts take colors, type sizes, and radii from tokens.
- **Match type and spacing to the scales.** Use the type sizes in the `DESIGNS.md` typography table and the 4px spacing scale. Do not invent sizes like `17px` or `22px` margins.
- **Keep the dashboard plain.** The dashboard is a work tool. Use glows, gradients, and large display type only on the sign-in screen and empty states. Data screens use flat surfaces, 1px borders, and `--font-small` and `--font-body` text.
- **Use the same words everywhere.** Call things by the names in `DESIGNS.md`: "agent", "run", "step", "tool call", "tool", "knowledge", "model", and "provider". Do not invent synonyms such as "bot", "assistant", or "job" for the same thing.
- **Write copy by the `DESIGNS.md` rules.** Use sentence case, no emojis, and no invented customers or numbers.

## Before you finish UI work

1. Run `./scripts/check.sh`. It includes the design check.
2. Run the changed app and look at it. Capture both widths with `scripts/screenshot.mjs`:

	```bash
	node scripts/screenshot.mjs http://localhost:5174/ /tmp/dashboard-1280.png 1280
	node scripts/screenshot.mjs http://localhost:5174/ /tmp/dashboard-390.png 390
	```

	A screen behind sign-in needs a session. Get one from the API and pass it in `LOCAL_STORAGE`:

	```bash
	session=$(curl -s -X POST -H 'Content-Type: application/json' -d '{"email":"<email>","password":"<password>"}' http://localhost:5174/api/v1/auth/token/)
	LOCAL_STORAGE=$(SESSION="$session" node -e 'console.log(JSON.stringify({"nextsci-agents.session": process.env.SESSION}))') \
	  node scripts/screenshot.mjs http://localhost:5174/agents /tmp/agents-1280.png 1280
	```

	The script prints a warning when the page scrolls sideways. Use it rather than Chrome's `--window-size`, which cannot go below 500px.
3. Capture both themes. Prefix the command with `COLOR_SCHEME=light` or `COLOR_SCHEME=dark` to emulate the OS setting, and look at each.
4. If you changed `design.css`, capture the sign-in screen and a shell screen. A token change shows up on both.
5. If you changed the theme store, the switch, or `index.html`, run `node scripts/e2e/theme.mjs http://localhost:5174/`. It checks the default, both overrides, a reload, and a bad saved value.
