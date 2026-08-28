import type {
  LeaderboardEntry,
  LeaderboardResponse,
  CategoryLeaderboardResponse,
  EdgeLeaderboardResponse,
  WalletProfile,
  AlertListResponse,
  FollowListResponse,
  FollowRecommendationResponse,
  FollowResponse,
  PortfolioResponse,
  PaperPositionListResponse,
  PaperTradeListResponse,
  PortfolioResetResponse,
  MarketDetailResponse,
  MarketListResponse,
  MarketSortKey,
} from "@/types/api";

const API_URL = "/api/v1";

function getHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (typeof window !== "undefined") {
    const key = localStorage.getItem("pm-api-key");
    if (key) headers["Authorization"] = `Bearer ${key}`;
  }
  return headers;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { ...init, headers: { ...getHeaders(), ...init?.headers } });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  // Leaderboard — root (no category, wallet_score ranking)
  leaderboard: (limit = 100, offset = 0) =>
    fetchJson<LeaderboardResponse>(`/leaderboard?limit=${limit}&offset=${offset}`),

  leaderboardEmerging: (limit = 10) =>
    fetchJson<LeaderboardEntry[]>(`/leaderboard/emerging?limit=${limit}`),

  leaderboardConsistent: (limit = 10) =>
    fetchJson<LeaderboardEntry[]>(`/leaderboard/consistent?limit=${limit}`),

  leaderboardEdge: (limit = 50, offset = 0) =>
    fetchJson<EdgeLeaderboardResponse>(`/leaderboard/edge?limit=${limit}&offset=${offset}`),

  // Leaderboard — by category
  categoryLeaderboard: (category: string, limit = 50, offset = 0) =>
    fetchJson<CategoryLeaderboardResponse>(`/leaderboard/${category}?limit=${limit}&offset=${offset}`),

  // Markets
  markets: (params: { category?: string; search?: string; sort?: MarketSortKey; limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.category && params.category !== "All") q.set("category", params.category);
    if (params.search) q.set("search", params.search);
    q.set("sort", params.sort ?? "volume");
    q.set("limit", String(params.limit ?? 50));
    q.set("offset", String(params.offset ?? 0));
    return fetchJson<MarketListResponse>(`/markets?${q.toString()}`);
  },

  marketDetail: (marketId: string) =>
    fetchJson<MarketDetailResponse>(`/markets/${marketId}`),

  // Wallets
  walletProfile: (address: string) =>
    fetchJson<WalletProfile>(`/wallets/${address}`),

  walletAlerts: (address: string, limit = 50, offset = 0) =>
    fetchJson<AlertListResponse>(`/alerts/${address}?limit=${limit}&offset=${offset}`),

  // Alerts
  alerts: (params?: { category?: string; min_score?: number; wallet?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams();
    if (params?.category) sp.set("category", params.category);
    if (params?.min_score) sp.set("min_score", String(params.min_score));
    if (params?.wallet) sp.set("wallet", params.wallet);
    if (params?.limit) sp.set("limit", String(params.limit));
    if (params?.offset) sp.set("offset", String(params.offset));
    const qs = sp.toString();
    return fetchJson<AlertListResponse>(`/alerts${qs ? `?${qs}` : ""}`);
  },

  // Follow
  listFollows: (active = true) =>
    fetchJson<FollowListResponse>(`/follow?active=${active}`),

  followWallet: (wallet: string, body: Record<string, unknown> = {}) =>
    fetchJson<FollowResponse>(`/follow/${wallet}`, { method: "POST", body: JSON.stringify(body) }),

  updateFollow: (wallet: string, body: Record<string, unknown>) =>
    fetchJson<FollowResponse>(`/follow/${wallet}`, { method: "PATCH", body: JSON.stringify(body) }),

  unfollowWallet: (wallet: string) =>
    fetchJson<void>(`/follow/${wallet}`, { method: "DELETE" }),

  followRecommendations: (limit = 20, offset = 0) =>
    fetchJson<FollowRecommendationResponse>(`/follow/recommendations?limit=${limit}&offset=${offset}`),

  // Portfolio
  portfolio: () =>
    fetchJson<PortfolioResponse>("/portfolio"),

  portfolioPositions: (status = "OPEN", limit = 50, offset = 0) =>
    fetchJson<PaperPositionListResponse>(`/portfolio/positions?status=${status}&limit=${limit}&offset=${offset}`),

  portfolioTrades: (limit = 50, offset = 0) =>
    fetchJson<PaperTradeListResponse>(`/portfolio/trades?limit=${limit}&offset=${offset}`),

  closePosition: (positionId: string) =>
    fetchJson<Record<string, unknown>>(`/portfolio/positions/${positionId}/close`, { method: "POST" }),

  resetPortfolio: (initialBalance = 10000) =>
    fetchJson<PortfolioResetResponse>("/portfolio/reset", { method: "POST", body: JSON.stringify({ initial_balance: initialBalance }) }),
};
