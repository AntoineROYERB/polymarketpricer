export interface LeaderEntry {
  wallet: string;
  category: string;
  num_trades: number;
  total_volume: number;
  total_pnl: number;
  roi: number;
  win_rate: number;
  profit_factor: number;
  is_specialist: boolean;
  category_rank: number;
  avg_position_size: number;
  avg_holding_duration: string;
}

export interface LeaderboardResponse {
  data: LeaderEntry[];
  limit: number;
  offset: number;
  category: string;
}

export interface WalletProfile {
  wallet: string;
  total_trades: number;
  total_volume: number;
  total_pnl: number;
  roi: number;
  win_rate: number;
  profit_factor: number;
  avg_position_size: number;
  avg_holding_duration: string;
  specialist_categories: string[];
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  num_resolved_positions: number;
  category: string;
}

export interface AlertItem {
  id: string;
  wallet: string;
  market_id: string;
  market_question: string;
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
  market_question: string;
  outcome: string;
  side: string;
  shares: number;
  entry_price: number;
  current_price: number;
  cost_basis: number;
  realized_pnl: number;
  unrealized_pnl: number;
  status: string;
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
  market_question: string;
  side: string;
  shares: number;
  price: number;
  amount_usd: number;
  pnl: number;
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
