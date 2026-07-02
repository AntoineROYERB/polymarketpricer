import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

export function useAlerts(params?: { category?: string; min_score?: number; wallet?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: ["alerts", params],
    queryFn: () => api.alerts(params),
  });
}

export function useWalletAlerts(address: string, limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["wallet-alerts", address, limit, offset],
    queryFn: () => api.walletAlerts(address, limit, offset),
    enabled: !!address,
  });
}

export function useFollowList(active = true) {
  return useQuery({
    queryKey: ["follows", active],
    queryFn: () => api.listFollows(active),
  });
}

export function useFollowRecommendations(limit = 20, offset = 0) {
  return useQuery({
    queryKey: ["follow-recommendations", limit, offset],
    queryFn: () => api.followRecommendations(limit, offset),
  });
}

export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: () => api.portfolio(),
  });
}

export function usePortfolioPositions(status = "OPEN", limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["portfolio-positions", status, limit, offset],
    queryFn: () => api.portfolioPositions(status, limit, offset),
  });
}

export function usePortfolioTrades(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["portfolio-trades", limit, offset],
    queryFn: () => api.portfolioTrades(limit, offset),
  });
}

export function useWalletProfile(address: string) {
  return useQuery({
    queryKey: ["wallet-profile", address],
    queryFn: () => api.walletProfile(address),
    enabled: !!address,
  });
}
