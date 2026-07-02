import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

export function useLeaderboard(limit = 100, offset = 0) {
  return useQuery({
    queryKey: ["leaderboard", limit, offset],
    queryFn: () => api.leaderboard(limit, offset),
  });
}

export function useCategoryLeaderboard(category: string, limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["leaderboard-category", category, limit, offset],
    queryFn: () => api.categoryLeaderboard(category, limit, offset),
    enabled: category !== "All",
  });
}
