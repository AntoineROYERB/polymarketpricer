# Phase 6 — Dashboard — Frontend Project Setup

> **Goal**: Scaffold a Next.js project with TypeScript, Tailwind CSS v4, and shadcn/ui in `frontend/`. Configure custom dark financial theme.
> **AI Agent Instructions**: Create the Next.js app, install dependencies, configure Tailwind with custom brand tokens, initialize shadcn/ui with a custom dark theme, set up project structure.

---

## Tech Stack

| Dependency | Version / Notes |
|---|---|
| Next.js | 15.x (App Router) |
| TypeScript | 5.x |
| Tailwind CSS | v4 |
| shadcn/ui | Latest (Radix UI primitives) |
| Recharts | For charts |
| Lucide React | Icons |
| @tanstack/react-query | Server state management |
| next-themes | Theme switching (dark mode only for now) |
| sonner | Toast notifications |
| date-fns | Date formatting |

---

## Setup Commands

```bash
mkdir frontend
cd frontend
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias="@/*"
npx shadcn@latest init
```

### shadcn/ui components to add
```bash
npx shadcn@latest add button card table dialog dropdown-menu input
npx shadcn@latest add badge tabs separator skeleton tooltip
npx shadcn@latest add select sheet command popover avatar
npx shadcn@latest add switch checkbox toast
```

---

## Design Direction: "The Edge Terminal"

> A surveillance-grade financial intelligence terminal — not another crypto dashboard. Every pixel signals precision instrumentation. Think Bloomberg Terminal meets mission-control interface.

### Core Concept
The user is an analyst tracking smart money movements. The interface should feel like operating precision equipment: authoritative, dense with information, warm where it matters (amber accents), ice-cold where it doesn't (dark backgrounds).

### Color Palette

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Background | Deep blue-black | `#08090a` | Page background |
| Surface | Dark slate | `#111316` | Cards, panels, sidebar |
| Surface hover | Slightly lighter | `#1a1d23` | Hover states |
| Border | Smoky gray | `#22262b` | Dividers, table borders |
| **Primary accent** | **Warm amber** | **`#f59e0b`** | Highlights, active states, KPIs |
| Bullish | Emerald | `#10b981` | Positive PnL, BUY indicators |
| Bearish | Rose | `#ef4444` | Negative PnL, SELL indicators |
| Info | Steel blue | `#3b82f6` | Links, info badges |
| Text primary | Off-white | `#f1f5f9` | Body text |
| Text secondary | Blue-gray | `#94a3b8` | Labels, meta, hints |
| Text muted | Gray | `#64748b` | Placeholders, disabled |

### Typography (deliberate, non-generic choices)

| Role | Font | Rationale |
|------|------|-----------|
| **Headings, large numbers** | **Fraunces** (Google Fonts, variable serif) | Warm, authoritative, unexpected in a financial dashboard. The "Soft" axis gives it a refined, almost literary feel. |
| **Data, tables, addresses** | **JetBrains Mono** (Google Fonts) | Technical, dense, readable at small sizes. Proper coding ligatures. |
| **Navigation, labels, body** | **DM Sans** (Google Fonts) | Clean, human, neutral — not Inter (the most overused sans in 2025-26). Pairs well with Fraunces. |

**Why this works**: A variable serif in a financial data dashboard is jarring and memorable. It signals: *this is not another generic crypto dashboard — this is serious analysis.* The amber accent (not the cliche neon green/cyan of every trading app) reinforces warmth, precision, and signal-over-noise.

### CSS Variables (`src/app/globals.css`)

```css
@theme {
  /* Backgrounds */
  --color-background: #08090a;
  --color-surface: #111316;
  --color-surface-hover: #1a1d23;
  --color-border: #22262b;
  --color-border-light: #2a2e35;

  /* Text */
  --color-text-primary: #f1f5f9;
  --color-text-secondary: #94a3b8;
  --color-text-muted: #64748b;

  /* Accents */
  --color-accent-amber: #f59e0b;
  --color-accent-emerald: #10b981;
  --color-accent-rose: #ef4444;
  --color-accent-blue: #3b82f6;

  /* Semantic */
  --color-bullish: #10b981;
  --color-bearish: #ef4444;

  /* Typography */
  --font-heading: "Fraunces", serif;
  --font-mono: "JetBrains Mono", monospace;
  --font-sans: "DM Sans", system-ui, sans-serif;
}
```

### Motion Language

| Interaction | Animation | Technique |
|-------------|-----------|-----------|
| Page load | Staggered reveal of sections (cards → table rows) | `animation-delay` + `translateY(8px)` → `translateY(0)` |
| Metric counters | Numbers count up on first render | CSS-only counter animation or `framer-motion` `useAnimate` |
| New WebSocket alert | Amber glow pulse + slide in from top | `@keyframes pulse-glow` + `translateY(-20px)` → `0` |
| Table row hover | Left border color shift (amber, or green/red per PnL direction) | `transition: border-color 150ms` |
| Navigation active | Amber left bar indicator | `2px solid var(--color-accent-amber)` |
| Data refresh | Subtle fade-pulse on updated cells | `@keyframes data-flash` (150ms) |

### Visual Texture & Details

- **Noise grain**: Subtle CSS noise texture overlay on `--color-background` via `background-image` with SVG filter
- **Grid lines**: Thin `1px` dotted `--color-border-light` on table backgrounds — reminiscent of financial graph paper
- **Monospace right-alignment**: All numeric columns in data tables are `text-right font-mono tabular-nums`
- **Dot separators**: Amber `●` dot dividers between sections in headers (not generic `|` pipes)
- **Focus ring**: Amber `2px` outline with `4px` offset — not the default blue

---

## Project Structure

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx           # Root layout with providers
│   │   ├── page.tsx             # Redirect to /leaderboard or login
│   │   ├── login/
│   │   │   └── page.tsx
│   │   ├── leaderboard/
│   │   │   └── page.tsx
│   │   ├── wallets/
│   │   │   └── [address]/
│   │   │       └── page.tsx
│   │   ├── feed/
│   │   │   └── page.tsx
│   │   ├── markets/
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   ├── follow/
│   │   │   └── page.tsx
│   │   └── portfolio/
│   │       └── page.tsx
│   ├── components/
│   │   ├── ui/                  # shadcn/ui components
│   │   ├── layout/
│   │   │   ├── sidebar.tsx
│   │   │   └── header.tsx
│   │   ├── shared/
│   │   │   ├── data-table.tsx
│   │   │   ├── metric-card.tsx
│   │   │   ├── sparkline.tsx
│   │   │   └── wallet-address.tsx
│   │   └── charts/
│   │       ├── bar-chart.tsx
│   │       └── sentiment-bar.tsx
│   ├── lib/
│   │   ├── api-client.ts        # Typed API client
│   │   ├── auth.ts              # Auth context / provider
│   │   └── utils.ts             # cn(), format helpers
│   ├── hooks/
│   │   ├── use-alerts.ts
│   │   ├── use-leaderboard.ts
│   │   └── use-websocket.ts
│   └── types/
│       └── api.ts               # Shared TypeScript types
├── public/
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── next.config.ts
```

---

## Root Layout Structure

```tsx
// src/app/layout.tsx
// - Providers: ThemeProvider (next-themes), AuthProvider, QueryClientProvider
// - AuthGate: redirects to /login if no API key stored
// - Sidebar navigation (collapsible)
// - Header bar (search, notifications, user menu)
// - Main content area
```

---

## .env.local

```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1/alerts/ws
```

---

## Verification

```bash
cd frontend
npm run dev          # opens http://localhost:3000
npm run build        # production build — must pass with 0 errors
npm run lint         # ESLint — 0 warnings
```
