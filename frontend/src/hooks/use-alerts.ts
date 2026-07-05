import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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

export function useMarketDetail(marketId: string) {
  return useQuery({
    queryKey: ["market-detail", marketId],
    queryFn: () => api.marketDetail(marketId),
    enabled: !!marketId,
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

export function useFollowWallet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ wallet, ...body }: { wallet: string; label?: string; auto_copy_enabled?: boolean; copy_mode?: string; copy_value?: number; category_filter?: string[] }) =>
      api.followWallet(wallet, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["follows"] });
      qc.invalidateQueries({ queryKey: ["follow-recommendations"] });
    },
  });
}

export function useUpdateFollow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ wallet, ...body }: { wallet: string; label?: string; auto_copy_enabled?: boolean; copy_mode?: string; copy_value?: number; category_filter?: string[]; active?: boolean }) =>
      api.updateFollow(wallet, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["follows"] });
    },
  });
}

export function useUnfollowWallet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (wallet: string) => api.unfollowWallet(wallet),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["follows"] });
      qc.invalidateQueries({ queryKey: ["follow-recommendations"] });
    },
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

export function useClosePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (positionId: string) => api.closePosition(positionId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio-positions"] });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      qc.invalidateQueries({ queryKey: ["portfolio-trades"] });
    },
  });
}

export function useResetPortfolio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (initialBalance: number) => api.resetPortfolio(initialBalance),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      qc.invalidateQueries({ queryKey: ["portfolio-positions"] });
      qc.invalidateQueries({ queryKey: ["portfolio-trades"] });
    },
  });
}

export function useWalletProfile(address: string) {
  return useQuery({
    queryKey: ["wallet-profile", address],
    queryFn: () => api.walletProfile(address),
    enabled: !!address,
  });
}
