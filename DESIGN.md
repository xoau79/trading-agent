# Dashboard Design System

This is the binding reference for `dashboard/dashboard.html` (and any future dashboard page). It exists so
the dashboard stays visually consistent as features are added over time — **every new color, spacing value,
radius, or component pattern must be added here in the same PR that introduces it.** Don't invent one-off
styles inline; use what's documented, or extend this doc first.

Everything below is extracted directly from the current, live dashboard CSS (`dashboard/css/app.css`) —
nothing here is aspirational.

## Architecture

The dashboard is a static app served by `dashboard_server.py` — no build step, no framework:

| File | Role |
|---|---|
| `dashboard/dashboard.html` | Shell: topbar, banner slot, grid of section containers |
| `dashboard/css/fonts.css` | Self-hosted `@font-face` (Space Grotesk, Inter, JetBrains Mono — `dashboard/fonts/*.woff2`) |
| `dashboard/css/app.css` | Every token and component below |
| `dashboard/js/util.js` | `window.U` — formatting, timestamp parsing, session windows, derived metrics, animated counters |
| `dashboard/js/charts.js` | `window.Charts` — canvas chart engine: `CandleChart` (zoom/pan/crosshair/trade markers), `LineChart`, `BarChart`, `BandChart`, `sparkline`, shared tooltip |
| `dashboard/js/components.js` | `window.C` — one render function per section; skeletons built once, updated in place so chart state survives the 60 s refresh |
| `dashboard/js/app.js` | Boot, `data.js` polling (script injection, works from file://), `/api/suggestions` polling, clock |
| `dashboard/js/demo.js` | Deterministic sample data, loaded only with `?demo=1` — preview the full UI without a running bot |

All user-facing dynamic strings go through `U.esc()` before touching `innerHTML`, or through
`textContent` (tooltips). Keep it that way.

## Color tokens

Defined once as CSS custom properties on `:root`, used everywhere via `var(--name)`. Never hardcode a hex
value in a rule when a token covers it. The five data colors were validated as a set (colorblind ΔE ≥ 12
between adjacent slots, ≥ 3:1 contrast on `--surface`) — if you change one, re-validate all five.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#07090F` | Page plane (with faint fixed grid + one radial glow via `.backdrop`) |
| `--surface` | `#0E1219` | Card/panel background; also the chart surface |
| `--surface-2` | `#131A26` | Nested surface (metric groups, position rows, feed hover, inputs) |
| `--surface-3` | `#182130` | Third step: active tabs, meters' tracks, hover states |
| `--line` | `rgba(151,168,199,.10)` | Default hairline border / gridline color family |
| `--line-2` | `rgba(151,168,199,.18)` | Stronger hairline (card hover, control borders) |
| `--ink` | `#EAF0F9` | Primary text |
| `--ink-2` | `#9DA9BC` | Secondary text |
| `--ink-3` | `#5E6B80` | Muted text, axis labels, eyebrows |
| `--accent` | `#5585E3` | The one brand accent: equity line, radar, links, selected chips, primary buttons |
| `--gold` | `#BC8A32` | Second data series / backtest progress / Monte-Carlo median |
| `--violet` | `#8377E0` | Third data series (rarely needed) |
| `--mc-band` | `#5585E3` | Monte-Carlo luck envelope fill (the shaded 5–95% / 25–75% bands in `BandChart`) — user-customizable, isolated from `--accent` so it can diverge without recolouring the rest of the UI |
| `--up` | `#27A874` | Profit **marks** (candles, bars, lines) |
| `--down` | `#DE4E56` | Loss **marks** |
| `--up-ink` / `--down-ink` | `#3DD68C` / `#F2646C` | Brighter steps reserved for P&L **text** at small sizes |
| `--warn-ink` | `#E5B567` | Warning/asleep text |

Rules: green always means profit/live, red always means loss/halted, amber always means waiting/degraded —
never decorative. Text never wears a mark color: numbers use `--up-ink`/`--down-ink`, marks use
`--up`/`--down`.

### Glow

`--glow` (0–2, Customize panel slider 0–200%) scales every accent-coloured glow effect. Each glow stacks
three box-shadow layers off two shared radius tokens — `--glow-near` (tight, brightest — reads as light at
the object's edge/outline), `--glow-mid` (short spread), `--glow-far` (soft, wide — the radiate-outward
falloff) — so intensity looks like it emanates from the source rather than a flat blur. Alpha (not radius)
carries the 0% = off behaviour: every layer's `color-mix()` percentage is `<base>% * var(--glow)`, so it's
fully transparent at `--glow:0` regardless of the radius tokens' floors. Elements using this recipe:
`.brand-mark`, `.card-title .accent-tick`, `.radar .core`, `.btn-primary`, `.streak-ring .halo`. Reuse the
three-layer pattern for new glow — never a single flat `box-shadow`.

### Colour hex entry

Every Customize colour swatch (`.cz-color-group`) pairs the native `<input type="color">` with a `.cz-hex`
text field — type a bare 6-character hex code (no `#`) to jump straight to that colour; it applies live
once 6 valid hex digits are present and reverts to the current value on blur otherwise. `customize.js`'s
`bindHex()` helper wires this — reuse it for any new colour control instead of a bare `<input type="color">`.

## Typography

Three self-hosted faces, each with one job (fallbacks: system-ui / ui-monospace):

- **Space Grotesk** (`--font-disp`) — display numerals only: hero capital, stat values, clock, asset
  symbols. Proportional figures at display sizes.
- **Inter** (`--font-ui`) — everything else. Card titles are 10–11px uppercase with `0.12–0.16em`
  letter-spacing.
- **JetBrains Mono** (`--font-mono`) — timestamps, prices, table numerics, axis ticks, deltas — always with
  `font-variant-numeric: tabular-nums` so columns align.

## Shape, spacing, motion

- **Radius scale** (don't add a fifth value): `7px` small controls · `10px` inner tiles/banners ·
  `16px` top-level `.card` · `999px` pills.
- **Grid**: 12-column `main.grid`, `gap: 18px`, page padding `28px`, `max-width: 2100px`, designed for
  1920×1200. Span classes: `.span-4/6/8/12`; composite columns `.col-left`, `.col-mid`, `.market-card`,
  `.agent-card`. Breakpoints: **1500px** (market chart drops below hero) and **1180px** (single column).
- **Card**: `--surface` + 1px `--line`, faint top-edge highlight gradient, `20px` padding. Hover only
  brightens the border — no lift/shadow inflation.
- **Motion**: one curve `--ease: cubic-bezier(.22,.61,.25,1)`; durations `150ms` (hover) / `280ms` /
  `~500ms` (reveals). Reveal-up on load, slide-in for new feed items, 650ms eased counter on the hero
  figure, 900ms streak-arc sweep. Everything collapses under `prefers-reduced-motion`.

## Components (reuse these, don't reinvent)

- **`.pill`** — status pill (topbar session, hero state). Variants: `-live` (green, pulsing dot),
  `-halt`, `-warn`, `-idle`, `-accent`.
- **`.banner`** — full-width callout under the topbar: `-halt`, `-asleep`, `-replay`, `-holiday`.
- **Hero** — `.hero-figure` (62px Space Grotesk, small `$`/cents), `.delta-chip` row, sparkline,
  status strip; **`.streak`** ring: SVG arc (fraction = |streak|/10), `up/down/flat` color states,
  breathing halo.
- **`.metric-group`** — the metrics panel's four sub-cards (Profit & loss / Edge / Averages / Risk), each a
  2×2 grid of `.m-cell` (label / display value / mono sub-line). All stats live here — don't scatter stats
  into other cards.
- **`.chart-shell`** — positioned container a chart engine instance owns; fixed heights via
  `.market-canvas`, `.equity-canvas`, `.mini-canvas`, `.bt-canvas(-sm)`. Never put a fixed height on the
  canvas itself. The shared tooltip `#chartTip` is a single fixed-position element.
- **Chart language** (enforced by `charts.js`, don't fork it): hairline solid gridlines, right-hand price
  axis, Sydney-time x labels, 2px lines, ≤ 24px bars with rounded data-ends (square at baseline), 2px
  surface rings on markers, crosshair + tooltip on every plot, empty-state message when there's no data.
- **`.stage-chip`** — per-asset strategy stage + bias, in the market card footer.
- **`.radar`** — the "agent is working" sweep (conic gradient + rings + blips). Pauses via
  `animationPlayState` when the bot isn't live. Keep it subtle; never add a spinner anywhere.
- **`.feed-item`** — timestamp (mono) + category tag + message; severity via `sev-success/-danger/-warn/-accent`
  left border + tag tint. The feed renders at most 18 items (`FEED_MAX` in components.js).
- **`.sugg`** — agent suggestion card (blue border = awaiting decision) with `.btn-approve` /
  `.btn-reject` pair.
- **`.btn`** — base button; variants `-primary` (accent gradient), `-approve`, `-reject`, `-wake`.
  Hover lifts 1px; that's the only translate in the system.
- **`.chip`** — selectable pill (Backtest Lab assets); `.sel` = accent tint.
- **`.meter` / `.prog`** — 5–6px rounded progress tracks; meter fill accent (refinement budget), prog fill
  gold (backtest).
- **Tables** — 10px uppercase `th`, hairline row borders, `.mono` numerics right-aligned, `.r-chip` for
  R-multiples, `.side-tag` for LONG/SHORT, expandable `.detail-row` for trade reflections.

## Adding something new

1. Check if an existing token/component covers it — reuse it.
2. If genuinely new, add it to this doc *and* implement it in the same PR.
3. New chart types go into `charts.js` sharing the same axis/tooltip/mark helpers — never a one-off canvas
   or an external chart library.
4. Keep the dark theme + single accent model. No second brand color, no light mode, without discussing
   first — deliberate constraint, not an oversight.
