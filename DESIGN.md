# Dashboard Design System

This is the binding reference for `dashboard/dashboard.html` (and any future dashboard page). It exists so
the dashboard stays visually consistent as features are added over time — **every new color, spacing value,
radius, or component pattern must be added here in the same PR that introduces it.** Don't invent one-off
styles inline; use what's documented, or extend this doc first.

Everything below is extracted directly from the current, live dashboard CSS — nothing here is aspirational.

## Color tokens

Defined once as CSS custom properties on `:root`, used everywhere else via `var(--name)`. Never hardcode a
hex value in a rule when a token already covers it.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0d1117` | Page background |
| `--card` | `#161b22` | Card/panel background |
| `--card2` | `#1c2230` | Nested surface (KPI tiles, table hover rows, dropdowns) |
| `--border` | `#2d333b` | All hairline borders |
| `--text` | `#e6edf3` | Primary text |
| `--dim` | `#8b949e` | Secondary/muted text |
| `--gold` | `#e3b341` | Primary accent — Gold trades, "run backtest" CTA, progress bars |
| `--green` | `#3fb950` | Positive/live/win state |
| `--red` | `#f85149` | Negative/halt/loss state |
| `--blue` | `#58a6ff` | Informational/replay state, links, suggestion cards |
| `--amber` | `#d29922` | Warning/asleep state |

Status colors are never used decoratively — `green` always means "good/live," `red` always means
"stopped/loss," `amber` always means "waiting/degraded." Don't repurpose them for anything else (e.g. don't
use `--red` for a delete button unrelated to trading state).

## Typography

- System font stack (no custom webfont — keeps the dashboard dependency-free and fast on localhost).
- Body text ~13–14px; KPI/stat numbers larger and bold; `.dim`/`--dim` for secondary labels.
- No more than two weights in play: regular body text, bold for numbers/headers/badges.

## Shape & spacing

- **Border radius scale** — pick from these, don't introduce a fourth value:
  - `8px` — buttons, inputs, small controls
  - `10px` — cards' inner elements (KPI tiles, stage cards, banners, chips-adjacent blocks)
  - `12px` — top-level `.card` panels
  - `999px` — fully-rounded pill shapes (badges, chips, progress/meter bars)
- **Layout**: single-column `.wrap` with `max-width: 1280px`, centered, `gap: 18px` between cards.
- **Grids**: `.cols2` (1fr 1fr), `.cols3` (repeat(3, 1fr)), `.colsHC` (2fr 1fr for hero+companion
  layouts), `.kpis` (`repeat(auto-fit, minmax(140px, 1fr))`). All collapse to a single column below the
  **950px** breakpoint — this is the one responsive breakpoint in use; don't add another without updating
  this doc.
- Card padding: `18px`. Inner tile padding: `12px 14px`.

## Components (reuse these, don't reinvent)

- **`.card`** — the base panel: `var(--card)` background, `1px solid var(--border)`, `12px` radius, `18px`
  padding. Every top-level section on the dashboard is a `.card`.
- **`.badge`** — small pill status label (`999px` radius). Variants: `.live` (green), `.halt` (red),
  `.idle` (dim/card2), `.asleep` (amber), `.holiday` (dim/card2).
- **`.banner`** — full-width callout, same variant naming as badges (`.halt`, `.replay`, `.asleep`,
  `.holiday`), `10px` radius, bold text, used for session-level state that deserves more attention than a
  badge.
- **`.kpi`** — a stat tile inside `.kpis`: `var(--card2)` background, `10px` radius.
- **`.stagecard`** — one card per traded asset showing its current strategy stage (building range /
  hunting / filtered / managing position); same visual weight as `.kpi`.
- **`.chip`** — selectable pill control (asset picker in Backtest Lab): `999px` radius, `.sel` variant uses
  `--blue` background/border when selected.
- **`.sugg`** — agent suggestion card: `var(--card2)` background, `1px solid var(--blue)` border (blue =
  informational, awaiting a decision), Approve (`.approve`, green) / Reject (`.reject`, red-outlined) button
  pair.
- **`.meter` / `.prog`** — thin rounded progress bars (`8px`/`10px` tall, `999px` radius track) with an
  inner fill div; `.meter` fill is blue (generic progress), `.prog` fill is gold (backtest progress).
- **`.feeditem`** — agent narration entries in the feed list; `k-entry` gets a green left border, `k-exit`
  gets a gold left border — every other kind is unaccented.
- Buttons: `border: none`, `8px` radius, `8px 16px` padding, font inherited. Primary actions (`.runbt`,
  `.wakebt`) use `--gold`/`--amber` fills with dark text for contrast; don't use light text on these two.

## Adding something new

Before writing new dashboard CSS:
1. Check if an existing token/component above already covers it — reuse it.
2. If genuinely new (a new state, a new data visualization type), add the token/component to this table
   *and* implement it, in the same PR.
3. Keep the dark theme + single accent-per-state model — don't introduce a second "brand color" or a light
   mode variant without discussing it first; this is a deliberate constraint, not an oversight.
