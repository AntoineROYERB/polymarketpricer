export interface LeaderboardEntry {
  rank: number;
  wallet: string;
  score: number;
  roi: number;
  win_rate: number;
  total_pnl: number;
  num_trades: number;
  consistency_score: number;
  experience_score: number;
  edge_score: number | null;
  edge_consistency: number | null;
  num_edge_trades: number | null;
}

export interface LeaderboardResponse {
  data: LeaderboardEntry[];
  limit: number;
  offset: number;
}

export interface CategoryLeaderboardEntry {
  rank: number;
  wallet: string;
  wallet_score: number | null;
  roi: number | null;
  win_rate: number | null;
  total_pnl: number | null;
  num_trades: number;
  total_volume: number | null;
  is_specialist: boolean;
}

export interface CategoryLeaderboardResponse {
  category: string;
  data: CategoryLeaderboardEntry[];
  limit: number;
  offset: number;
}

export interface WalletProfile {
  wallet: string;
  main_wallet: string | null;
  label: string | null;
  is_tracked: boolean;
  first_seen: string | null;
  last_seen: string | null;
  last_position_sync: string | null;
  last_trade_sync: string | null;
  analytics: WalletAnalyticsData | null;
  current_positions: PositionSummary[];
  rank: number | null;
  categories: WalletCategorySummary[];
  edge_metrics: EdgeMetrics | null;
}

export interface WalletAnalyticsData {
  total_pnl: number | null;
  roi: number | null;
  win_rate: number | null;
  num_trades: number | null;
  total_volume: number | null;
  avg_position_size: number | null;
  sharpe_ratio: number | null;
  profit_factor: number | null;
  max_drawdown: number | null;
  avg_holding_duration: string | null;
  consistency_score: number | null;
  experience_score: number | null;
}

export interface PositionSummary {
  market_id: string;
  question: string;
  event_slug: string | null;
  condition_id: string | null;
  side: string | null;
  status: string;
  shares: number;
  avg_entry_price: number;
  entry_time: string | null;
  exit_time: string | null;
  realized_pnl: number | null;
  unrealized_pnl: number | null;
  total_pnl: number | null;
}

export interface WalletCategorySummary {
  category: string;
  num_trades: number;
  total_volume: number | null;
  total_pnl: number | null;
  roi: number | null;
  win_rate: number | null;
  profit_factor: number | null;
  avg_position_size: number | null;
  is_specialist: boolean;
  category_rank: number | null;
}

export interface EdgeMetrics {
  wallet: string;
  snapshot_date: string | null;
  avg_edge: number;
  median_edge: number | null;
  edge_consistency: number | null;
  edge_volatility: number | null;
  edge_score: number | null;
  num_edge_trades: number;
}

export interface AlertItem {
  id: string;
  wallet: string;
  market_id: string;
  market_question: string;
  event_slug: string | null;
  condition_id: string | null;
  action: string;
  category: string;
  price: number;
  position_size: number;
  wallet_score: number;
  detected_at: string;
}

export interface AlertListResponse {
  data: AlertItem[];
  limit: number;
  offset: number;
}

export interface FollowResponse {
  id: string;
  wallet: string;
  label: string | null;
  active: boolean;
  auto_copy_enabled: boolean;
  copy_mode: string;
  copy_value: number;
  category_filter: string[];
  followed_at: string;
  updated_at: string | null;
  unfollowed_at: string | null;
}

export interface FollowListResponse {
  data: FollowResponse[];
  total: number;
}

export interface FollowRecommendation {
  wallet: string;
  follow_score: number;
  reasons: string[];
}

export interface FollowRecommendationResponse {
  data: FollowRecommendation[];
  limit: number;
  offset: number;
}

export interface PortfolioResponse {
  id: string | null;
  name: string;
  initial_balance: number;
  current_balance: number;
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  total_pnl: number;
  total_roi: number;
  total_trades: number;
  total_volume: number;
}

export interface PaperPositionResponse {
  id: string;
  market_id: string;
  event_slug: string | null;
  condition_id: string | null;
  outcome: string;
  side: string;
  status: string;
  shares: number;
  avg_entry_price: number;
  current_price: number | null;
  cost_basis: number;
  realized_pnl: number;
  unrealized_pnl: number | null;
  followed_wallet: string;
  opened_at: string;
  closed_at: string | null;
}

export interface PaperPositionListResponse {
  data: PaperPositionResponse[];
  total: number;
}

export interface PaperTradeResponse {
  id: string;
  market_id: string;
  event_slug: string | null;
  condition_id: string | null;
  outcome: string;
  side: string;
  shares: number;
  price: number;
  amount_usd: number;
  followed_wallet: string;
  copy_mode: string | null;
  copy_value_used: number | null;
  executed_at: string;
}

export interface PaperTradeListResponse {
  data: PaperTradeResponse[];
  limit: number;
  offset: number;
  total: number;
}

export interface PortfolioResetResponse {
  portfolio: PortfolioResponse;
  message: string;
}

// ── Phase 6: Market Detail ───────────────────────────────────────────

export interface OutcomeResponse {
  id: string;
  label: string;
  price: number | null;
  winner: boolean | null;
}

export interface ActiveTraderEntry {
  wallet: string;
  side: string | null;
  position_size: number | null;
  price: number | null;
  total_pnl: number | null;
}

export interface MarketDetailResponse {
  id: string;
  question: string;
  category: string | null;
  event_slug: string | null;
  condition_id: string | null;
  volume_usd: number | null;
  liquidity_usd: number | null;
  close_time: string | null;
  created_at: string | null;
  resolved_at: string | null;
  winning_outcome: string | null;
  outcomes: OutcomeResponse[];
  buy_percent: number;
  active_traders: ActiveTraderEntry[];
}

// ── Phase 6: Edge / Emerging / Consistent Leaderboard ────────────────

export interface EdgeLeaderboardEntry {
  wallet: string;
  edge_score: number;
  avg_edge: number;
  edge_consistency: number | null;
  num_edge_trades: number;
  rank: number;
}

export interface EdgeLeaderboardResponse {
  data: EdgeLeaderboardEntry[];
  limit: number;
  offset: number;
}

export interface LeaderboardRow {
  rank: number;
  wallet: string;
  score?: number;
  wallet_score?: number | null;
  roi?: number | null;
  win_rate?: number | null;
  total_pnl?: number | null;
  num_trades?: number;
  total_volume?: number | null;
  edge_score?: number | null;
  avg_edge?: number;
  edge_consistency?: number | null;
  num_edge_trades?: number | null;
  is_specialist?: boolean;
}

export type LeaderboardTabType = "main" | "emerging" | "consistent" | "edge" | "category";
