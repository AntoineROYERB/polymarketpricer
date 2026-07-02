import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";

export function useLeaderboard(category: string, limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["leaderboard", category, limit, offset],
    queryFn: () => api.leaderboard(category, limit, offset),
  });
}
