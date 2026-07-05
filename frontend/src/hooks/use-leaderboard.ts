import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { LeaderboardTabType, LeaderboardEntry } from "@/types/api";

export function useLeaderboard(limit = 100, offset = 0) {
  return useQuery({
    queryKey: ["leaderboard", limit, offset],
    queryFn: () => api.leaderboard(limit, offset),
  });
}

export function useEmergingLeaderboard(limit = 10) {
  return useQuery({
    queryKey: ["leaderboard-emerging", limit],
    queryFn: () => api.leaderboardEmerging(limit),
  });
}

export function useConsistentLeaderboard(limit = 10) {
  return useQuery({
    queryKey: ["leaderboard-consistent", limit],
    queryFn: () => api.leaderboardConsistent(limit),
  });
}

export function useEdgeLeaderboard(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["leaderboard-edge", limit, offset],
    queryFn: () => api.leaderboardEdge(limit, offset),
  });
}

export function useCategoryLeaderboard(category: string, limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["leaderboard-category", category, limit, offset],
    queryFn: () => api.categoryLeaderboard(category, limit, offset),
    enabled: category !== "All",
  });
}

interface TabResult {
  data: LeaderboardEntry[];
  isLoading: boolean;
}

export function useLeaderboardForTab(tab: LeaderboardTabType, category: string, limit = 100, offset = 0): TabResult {
  const { data: main, isLoading: loadingMain } = useLeaderboard(tab === "main" ? limit : 100, tab === "main" ? offset : 0);
  const { data: emerging, isLoading: loadingEmerging } = useEmergingLeaderboard(10);
  const { data: consistent, isLoading: loadingConsistent } = useConsistentLeaderboard(10);
  const { data: edge, isLoading: loadingEdge } = useEdgeLeaderboard(50, tab === "edge" ? offset : 0);
  const { data: cat, isLoading: loadingCat } = useCategoryLeaderboard(category, 50, tab === "category" ? offset : 0);

  let data: LeaderboardEntry[] = [];
  let isLoading = true;

  switch (tab) {
    case "main":
      data = main?.data ?? [];
      isLoading = loadingMain;
      break;
    case "emerging":
      data = emerging ?? [];
      isLoading = loadingEmerging;
      break;
    case "consistent":
      data = consistent ?? [];
      isLoading = loadingConsistent;
      break;
    case "edge": {
      data = (edge?.data ?? []) as unknown as LeaderboardEntry[];
      isLoading = loadingEdge;
      break;
    }
    case "category":
      data = (cat?.data ?? []) as unknown as LeaderboardEntry[];
      isLoading = loadingCat;
      break;
  }

  return { data, isLoading };
}
