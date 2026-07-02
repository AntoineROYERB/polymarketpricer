# Phase 6 — Dashboard — API Client & Shared Components

> **Goal**: Build a typed API client for all backend endpoints, shared layout, and reusable UI components.
> **AI Agent Instructions**: Create `src/lib/api-client.ts`, `src/types/api.ts`, shared layout components (`sidebar`, `header`), and reusable components (`data-table`, `metric-card`, etc.).

---

## Typed API Client (`src/lib/api-client.ts`)

```typescript
// Axios-based client with:
// - Base URL from NEXT_PUBLIC_API_URL
// - Authorization header from stored API key
// - Error interceptor (401 → redirect to /login)
// - TypeScript generics for all endpoints

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: process.env.NEXT_PUBLIC_API_URL,
    });
    this.client.interceptors.request.use((config) => {
      const key = localStorage.getItem("api_key");
      if (key) config.headers.Authorization = `Bearer ${key}`;
      return config;
    });
    this.client.interceptors.response.use(
      (r) => r,
      (err) => {
        if (err.response?.status === 401) {
          localStorage.removeItem("api_key");
          window.location.href = "/login";
        }
        return Promise.reject(err);
      }
    );
  }

  // Leaderboard
  async getLeaderboard(params?: { limit?; offset? }): Promise<LeaderboardResponse>
  async getEmerging(params?): Promise<LeaderboardResponse>
  async getConsistent(params?): Promise<LeaderboardResponse>
  async getEdgeLeaderboard(params?): Promise<EdgeLeaderboardResponse>
  async getCategoryLeaderboard(category: string, params?): Promise<CategoryLeaderboardResponse>

  // Wallets
  async getWallet(address: string): Promise<WalletProfile>
  async getWalletEdge(address: string): Promise<WalletEdgeResponse>
  async getWalletCategories(address: string): Promise<WalletCategoryResponse>
  async getWalletCategory(address: string, category: string): Promise<CategoryDetailResponse>

  // Markets
  async getMarkets(params?): Promise<MarketListResponse>

  // Alerts
  async getAlerts(params?): Promise<AlertListResponse>

  // Follow
  async getFollowRecommendations(params?): Promise<FollowRecommendationResponse>
  async getCategoryFollowLeaderboard(category: string, params?)
  async getWalletCategoryScores(wallet: string)
  async getFollowedWallets(): Promise<FollowListResponse>
  async followWallet(wallet: string, body: FollowCreate)
  async updateFollow(wallet: string, body: FollowUpdate)
  async unfollowWallet(wallet: string)

  // Portfolio
  async getPortfolio(): Promise<PortfolioResponse>
  async getPositions(): Promise<PaperPositionListResponse>
  async getTrades(params?): Promise<PaperTradeListResponse>
  async closePosition(positionId: string)
  async resetPortfolio(body: PortfolioResetRequest)
}
```

---

## TypeScript Types (`src/types/api.ts`)

Generate types that mirror the backend Pydantic schemas:

```typescript
// Mirror of backend response types — 1:1 with schemas.py
export interface LeaderboardEntry { rank: number; wallet: string; ... }
export interface AlertItem { id: string; wallet: string; ... }
export interface FollowResponse { id: string; wallet: string; ... }
// etc.
```

---

## WebSocket Hook (`src/hooks/use-websocket.ts`)

```typescript
// useWebSocket hook
// - Connects to NEXT_PUBLIC_WS_URL?api_key=<key>
// - Auto-reconnect on disconnect
// - Parses JSON messages
// - Returns { lastMessage, isConnected, alerts }
```

---

## Shared Layout Components

### Sidebar (`src/components/layout/sidebar.tsx`)
- Fixed left sidebar (w: 64px collapsed, 220px expanded)
- Dark slate `--color-surface` background, slightly darker than page
- Navigation items: amber dot-matrix icon + label on expand
- Active route: amber left border `2px` + subtle bg highlight
- Items: Leaderboard (🏛️ abstract), Feed (📡), Markets (📊), Follow (🔗), Portfolio (💼)
- Bottom section: API key indicator (green dot if set), Logout
- Collapse toggle button at bottom
- **Edge Terminal detail**: Thin amber horizontal rule above bottom section, `1px dotted --color-border-light`

### Header (`src/components/layout/header.tsx`)
- Full-width bar at top (h: 56px)
- Left: "EDGE TERMINAL" wordmark in `Fraunces` (stylized, letter-spaced)
- Right group:
  - Search input (wallet address lookup, `font-mono`)
  - WebSocket connection dot: `●` green (connected) / red (disconnected)
  - User menu: API key status + logout
- Bottom border: `1px solid --color-border`, with subtle amber glow on left 20%

### Data Table (`src/components/shared/data-table.tsx`)
- Generic table component using shadcn/ui Table
- **Edge-specific details**:
  - Monospace font for all numeric cells (`font-mono tabular-nums text-right`)
  - Right-aligned numeric columns (like terminal)
  - Amber top border flash on hovered row
  - Alternating row backgrounds (very subtle: `#0d0f12` on even rows)
- Sortable columns (click header to sort, amber arrow indicator)
- Pagination controls (previous/next with offset)
- Loading skeleton state (8 rows of pulsing amber-tinted blocks)
- Empty state with "No data" message and subtle icon
- Props: `columns`, `data`, `loading`, `total`, `limit`, `offset`, `onOffsetChange`

### Metric Card (`src/components/shared/metric-card.tsx`)
```tsx
interface MetricCardProps {
  label: string;
  value: string | number;
  change?: number;           // % change, color-coded
  icon?: React.ReactNode;
  trend?: "up" | "down" | "neutral";
  loading?: boolean;
}
```
- **Edge-specific details**:
  - Card background: `--color-surface` with `1px solid --color-border`
  - Large value in `Fraunces` (the serif makes big numbers feel weighty)
  - Label in `DM Sans` uppercase, letter-spaced, `--color-text-muted`
  - Change indicator: emerald/rose colored, with small arrow
  - On load: value counter animates from 0 → final (CSS `@property` or IntersectionObserver)
  - On hover: subtle amber border glow

### Animated Metric Counter (`src/components/shared/animated-counter.tsx`)
```tsx
interface AnimatedCounterProps {
  value: number;
  duration?: number;         // ms, default 800
  prefix?: string;           // "$", "+", etc.
  suffix?: string;           // "%", "x", etc.
  decimals?: number;         // default 2
  className?: string;
}
```
- Counts from 0 to `value` on mount using `requestAnimationFrame`
- Formatted with Intl.NumberFormat (commas, decimals)
- Pairs with metric cards for the "numbers populating" effect

### Wallet Address (`src/components/shared/wallet-address.tsx`)
- Truncated display: `0x1234...abcd` (monospace)
- Click → copies full address to clipboard + amber toast
- Hover: subtle amber underline
- Link to `/wallets/{address}`

### Charts (`src/components/charts/`)

#### `bar-chart.tsx` — Category breakdown
- Recharts `BarChart` wrapper
- Each bar colored by category (auto-assigned palette from categorical colors)
- Hover: tooltip with wallet count + avg ROI
- Domain: [0, max] with grid lines matching `--color-border-light`

#### `sentiment-bar.tsx` — BUY/SELL ratio
- Horizontal stacked bar
- Emerald (BUY) fills from left, Rose (SELL) from right
- Center pivot line at 50%
- Labels: "XX% Bullish" / "XX% Bearish" in `font-mono`
- Thin amber border around the bar

#### `sparkline.tsx` — Mini line chart
- Recharts `AreaChart` wrapper, 150x40px
- Single smooth line, no axis, no grid
- Color determined by trend direction (emerald/rose)
- Filled area with low opacity gradient
- Hover: dot tooltip with value

---

## Files to Create

| Action | Path |
|--------|------|
| CREATE | `src/types/api.ts` |
| CREATE | `src/lib/api-client.ts` |
| CREATE | `src/hooks/use-websocket.ts` |
| CREATE | `src/hooks/use-leaderboard.ts` |
| CREATE | `src/hooks/use-alerts.ts` |
| CREATE | `src/components/layout/sidebar.tsx` |
| CREATE | `src/components/layout/header.tsx` |
| CREATE | `src/components/shared/data-table.tsx` |
| CREATE | `src/components/shared/metric-card.tsx` |
| CREATE | `src/components/shared/wallet-address.tsx` |
| CREATE | `src/components/charts/bar-chart.tsx` |
| CREATE | `src/components/charts/sentiment-bar.tsx` |
| CREATE | `src/components/charts/sparkline.tsx` |

---

## Verification

```tsx
// Test: API client returns typed responses
const api = new ApiClient();
const data = await api.getLeaderboard({ limit: 10 });
// data should be typed as LeaderboardResponse

// Test: Data table renders with mock data
// Test: Sidebar highlights active route
// Test: Wallet address truncation + copy
```
