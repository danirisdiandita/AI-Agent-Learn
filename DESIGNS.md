# Design system

Nextsci Agents uses one visual language across the dashboard. It is quiet and precise, and it comes in a dark theme and a light theme. Content carries the color. The interface around it stays neutral.

The dashboard renders these tokens through shadcn/ui components on Tailwind CSS. `dashboard/src/tailwind.css` maps shadcn's names to the tokens. [`.agents/ui.md`](.agents/ui.md) has the rules.

The tokens below exist as CSS custom properties in [`dashboard/src/design.css`](dashboard/src/design.css). Use the variables in code. Do not paste raw hex values into components.

## Principles

- **Dark first, light equal.** The dark base is near-black, not gray, and the light base is near-white. Surfaces lift by a few steps of lightness, never by heavy shadows. Every screen must work in both themes.
- **Color means data.** Neutral grays build the interface. Saturated color marks agents, tools, chart series, and status. One accent color marks the primary action.
- **Thin lines, soft light.** Separate regions with 1px borders at low opacity. Use a faint radial glow for emphasis instead of solid fills.
- **Tight, confident type.** Large headings use negative letter spacing and short line height. Body text stays small and calm.
- **Show the product.** Every claim on the sign-in screen sits next to a picture of the interface that does it.
- **Motion is a hint.** Fade and lift by a few pixels. Never bounce or spin. Respect `prefers-reduced-motion`.

## Color

### Themes

The dashboard offers three choices: **System**, **Light**, and **Dark**. System is the default and follows the operating system, including when it changes while the page is open. The choice is saved per browser.

- **Tokens hold both values.** Every color token in `design.css` is `light-dark(<light>, <dark>)`. CSS `color-scheme` picks the side: `light dark` by default, or one side when `<html>` has `data-theme="light"` or `data-theme="dark"`.
- **The store.** `src/hooks/useTheme.ts` keeps the choice in a zustand store persisted to `localStorage` under `nextsci-agents.theme`, and sets or removes `data-theme`. An inline script in `index.html` applies a saved choice before the first paint.
- **The switch.** A three-button group with Monitor, Sun, and Moon icons, labeled "System theme", "Light theme", and "Dark theme". The dashboard builds it from the shadcn toggle group (`src/components/ThemeToggle.tsx`). It sits in the shell header, and at the top right of the sign-in screen.
- **Tints mix a token.** For a translucent color, mix a token with transparent, such as `color-mix(in srgb, var(--text) 10%, transparent)` for a hairline that is white on dark and black on light. Never write `rgb()` with fixed values outside `design.css`.

### Neutrals

| Token | Dark | Light | Use |
| --- | --- | --- | --- |
| `--bg` | `#08090a` | `#fcfcfd` | Page background |
| `--bg-raised` | `#0e0f10` | `#f5f6f7` | Alternate section background |
| `--surface` | `#131416` | `#ffffff` | Cards, panels, window frames |
| `--surface-hover` | `#1a1b1e` | `#f3f4f5` | Hover state of a surface |
| `--surface-inset` | `#0b0c0d` | `#f1f2f4` | Inputs, code blocks, run graph background |
| `--border` | `rgb(255 255 255 / 0.08)` | `rgb(15 16 18 / 0.09)` | Default 1px border |
| `--border-strong` | `rgb(255 255 255 / 0.14)` | `rgb(15 16 18 / 0.17)` | Hovered or focused border |
| `--text` | `#f7f8f8` | `#0f1012` | Headings and primary text |
| `--text-2` | `#c9ced6` | `#3c4047` | Body text |
| `--text-3` | `#8a8f98` | `#696e77` | Secondary text and captions |
| `--text-4` | `#5d6168` | `#9a9ea6` | Disabled text and fine print |
| `--shadow` | `#000000` | `rgb(15 16 18 / 0.18)` | Base for drop shadows; mix it, such as `color-mix(in srgb, var(--shadow) 70%, transparent)` |

### Accent and status

| Token | Dark | Light | Use |
| --- | --- | --- | --- |
| `--accent` | `#5e9bff` | `#2f6fe0` | Links, focus rings, primary highlights |
| `--accent-soft` | `rgb(94 155 255 / 0.14)` | `rgb(47 111 224 / 0.12)` | Accent backgrounds and glows |
| `--success` | `#4cc38a` | `#1d9460` | Run succeeded, tool call returned |
| `--warning` | `#f5b544` | `#b7791f` | Run waiting, near a step or token limit |
| `--danger` | `#ef5a5a` | `#d93636` | Run failed, tool call errored |
| `--danger-text` | `#f6a4a4` | `#b42323` | Error message text on a `--danger` tint |
| `--fill-primary` | `#e8e9ea` | `#0f1012` | Primary button background |
| `--fill-primary-hover` | `#ffffff` | `#2b2d31` | Primary button background on hover |

### Series colors

Each agent, tool, or chart series gets one series color. Assign colors in this order, and reuse them in the same order after the sixth.

| Token | Dark | Light |
| --- | --- | --- |
| `--series-1` | `#5e9bff` | `#2f6fe0` |
| `--series-2` | `#f2994a` | `#e07b25` |
| `--series-3` | `#4cc38a` | `#1d9460` |
| `--series-4` | `#c084fc` | `#9b5de5` |
| `--series-5` | `#f5c451` | `#c99a0e` |
| `--series-6` | `#38c6d9` | `#1a9fb4` |

## Typography

Use [Inter](https://rsms.me/inter/) with the variable weight axis. Enable the `cv11`, `ss01`, and `ss03` font features for the single-story `a` and the straight digits.

| Token | Size | Line height | Weight | Letter spacing | Use |
| --- | --- | --- | --- | --- | --- |
| `--font-display` | `clamp(44px, 7vw, 80px)` | 1.02 | 600 | -0.035em | Display heading |
| `--font-h2` | `clamp(32px, 4.4vw, 52px)` | 1.08 | 600 | -0.03em | Section headings |
| `--font-h3` | `20px` | 1.3 | 560 | -0.012em | Card titles |
| `--font-lead` | `clamp(17px, 1.6vw, 20px)` | 1.55 | 400 | -0.005em | Text under a heading |
| `--font-body` | `15px` | 1.6 | 400 | 0 | Body text |
| `--font-small` | `13px` | 1.5 | 500 | 0 | Labels, captions, UI text |
| `--font-mono` | `13px` | 1.6 | 400 | 0 | Code, using `ui-monospace` |

Headings use `--text`. Give display headings a vertical gradient from `--text` to 55% opacity. Body text uses `--text-2`. Do not make body text pure white.

## Space, size, and shape

- **Spacing.** Use a 4px grid: 4, 8, 12, 16, 24, 32, 48, 64, 96, 128.
- **Content width.** Keep content at most 1120px wide (`--content`). Keep text blocks at most 640px wide.
- **Radius.** `--radius-sm` 6px for buttons and chips, `--radius` 10px for cards, and `--radius-lg` 16px for large frames, such as the run graph on the sign-in screen.
- **Elevation.** A raised surface has a 1px `--border` plus an inner top highlight, `--highlight`.

## Components

The buttons, the `.brand` logo lockup, and the `.dot` status marker live in the shared components section of `design.css`. Use those classes as they are. The components below that section are specified here, and the dashboard builds them from tokens.

The logo is `dashboard/public/favicon.svg`: an N drawn as a run, three finished steps in `#f7f8f8` and the live step in dark-theme `--accent` blue, on a `#08090a` tile with a faint light edge so it holds on dark backgrounds. Render it with an `<img>` element. Do not inline a copy of its SVG.

### Buttons

| Variant | Background | Text | Border | Use |
| --- | --- | --- | --- | --- |
| Primary | `--fill-primary` | `--bg` | none | One main action per view |
| Secondary | `--surface` | `--text` | `--border` | Other actions |
| Ghost | transparent | `--text-3` | none | Navigation and tertiary actions |

Buttons are 36px tall. They use `--font-small` at weight 560 and `--radius-sm`. On hover, primary buttons move to `--fill-primary-hover` and secondary buttons switch to `--border-strong`.

### Pill

A pill is a small rounded label above a heading, such as a release note. It has a `--surface` background, a `--border`, `--font-small`, and an optional colored dot.

### Eyebrow

An eyebrow is a short label above a section heading. It uses `--font-small`, `--accent`, and weight 560. It is never all caps.

### Card

A card has a `--surface` background, a `--border`, `--radius`, and 24px padding. Its contents are an icon, then a title in `--font-h3`, then body text in `--text-3`. On hover, the border changes to `--border-strong`. Cards never move on hover.

### Run graph

A run graph shows an agent and the steps it took. Draw it with SVG on `--surface-inset`, over a grid of 1px lines in `--text` at about 6%, through `color-mix()`. Draw the agent as a `--text` square. Draw each branch of steps as a 2.5px line in a series color with round joins. Draw each step as a circle with a 2px outline: filled with the series color when it finished, hollow when it is still to come. The step that runs now pulses, and stops pulsing under `prefers-reduced-motion`.

### Icons

Draw icons as 16px or 20px inline SVG, with a 1.5px stroke, round caps, `currentColor`, and no fill. Put a feature icon in a 32px square with `--surface-hover` and `--radius-sm`.

## Sign-in screen

The dashboard opens on the sign-in screen at [`SignInPage.tsx`](dashboard/src/features/auth/components/SignInPage.tsx). From 1024px wide it splits in two. The form sits on the left on `--bg`. The brand panel ([`SignInBrand.tsx`](dashboard/src/features/auth/components/SignInBrand.tsx)) sits on the right on `--bg-raised` behind a 1px `--border`. The panel holds the logo and "Nextsci", an eyebrow, a heading at `--font-h2` with the heading gradient, the lead, the run graph in a 16px-radius frame (scaled to fit, so every route stays in view, with its grid filling the rest of the frame), and three value facts. Below 1024px the panel hides and the form centers over a faint accent glow. The form is a 360px column. It holds the logo, a 24px heading, one line of `--text-3`, two inputs, and one full-width primary button. Inputs are 40px tall on `--surface-inset`. Their focus state is an `--accent` border with an `--accent-soft` ring. Errors appear above the button in a `--danger` tinted box with `role="alert"`. There is no sign-up link, because an administrator creates accounts.

## Dashboard shell

After sign-in, the dashboard shows a sidebar beside the active section. Each section has its own URL, such as `/agents` or `/runs`, and the active section is the one whose route matched. The shell lives in [`dashboard/src/app/shell/AppShell.tsx`](dashboard/src/app/shell/AppShell.tsx), the sidebar in [`AppSidebar.tsx`](dashboard/src/app/shell/AppSidebar.tsx), the list of sections in [`sections.ts`](dashboard/src/app/shell/sections.ts), and the routes in [`router.tsx`](dashboard/src/app/router.tsx). To add a section, add its entry to `sections.ts` and its route to `router.tsx`.

- **Sidebar.** 256px wide on `--bg-raised`, with a 1px `--border` on its right edge. The header holds the logo and "Nextsci". The middle holds one 36px link per section, each with a 16px icon and a `--font-small` label at weight 500. Each item is a real link, so a middle-click or Ctrl-click (⌘-click on a Mac) opens the section in a new tab. The footer holds the account button: an initial on a 24px circle and the email. The account button opens a menu with **Sign out**, which first asks "Sign out?" in an alert dialog with Cancel and Sign out buttons. Cancel, Escape, or a click outside keeps the session.
- **Item states.** Labels use `--text-2` and icons use `--text-3`. The active item has `aria-current="page"`, and it has a fill of `--text` mixed at 5%, the inner top highlight, and `--text` for both icon and label. On hover, the item gets 60% of that fill. The fill is a tint rather than `--surface-hover`, because `--surface-hover` almost matches `--bg-raised` in the light theme. Keyboard focus shows the standard 2px `--accent` outline.
- **Collapsed.** The sidebar narrows to a 52px icon rail. Labels fade out, and each icon shows its label in a tooltip on hover. Every icon, the logo, and the avatar center on the same vertical line in both states, and every label starts at the same x, so nothing moves sideways. Toggle it with the header button, the rail on the sidebar edge, or Ctrl+B (⌘B on a Mac). A cookie keeps the choice across reloads.
- **Motion.** The width changes over 200ms with ease-out. It stops under `prefers-reduced-motion: reduce`.
- **Phone.** Under 768px the sidebar is a sheet that slides in from the left over the page, dimmed by `--shadow` at 70%. Choosing a section closes it.
- **Main area.** A 56px header holds the sidebar toggle and the section name on the left, and the theme switch on the right. Its bottom border lines up with the sidebar header's border. Below it, the section's empty state is centered: the section icon in a 40px raised square, a 20px title, and a short `--text-3` sentence that says the feature is planned. The browser tab shows the section name and the product, such as "Agents · Nextsci".
- **Agents chat.** `/agents` shows a chat built from shadcn parts, in a column at most 720px wide. Before the first message it shows the Empty state with three suggestion buttons that send their text. The user's messages sit right on a `bg-muted` bubble. The model's replies sit left under a small Bot avatar and a "Model" label, in `--text-2`. While waiting, a spinner sits beside the avatar. An error is an Alert on a `--danger` tint with `--danger-text`. The composer is an InputGroup card: a textarea (Enter sends, Shift+Enter adds a line), then a row with **New chat**, the key hints in Kbd, and a round primary send button.
- **Not found.** Any other path shows the not-found page inside the shell. It uses the empty-state layout with a search icon, the title "Page not found", one sentence, and a primary **Go to Agents** button. The header and the browser tab say "Page not found", and no sidebar item is active.

## Writing on the page

- Describe what the product does. Name the mechanism, such as "tool calls" or "token limits".
- Do not invent customers, logos, quotes, or numbers. The project is in early development, so mark planned features as planned.
- Use sentence case for headings and buttons.
- Use no emojis.

## Accessibility

- Text meets WCAG AA contrast on its background. `--text-3` on `--bg` is the lowest contrast allowed for body copy.
- Every interactive element has a visible focus ring, a 2px `--accent` outline with a 2px offset.
- Decorative SVGs have `aria-hidden="true"`. Pictures of the interface have a text alternative that describes what they show.
- Animations stop under `prefers-reduced-motion: reduce`.
