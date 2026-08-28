import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import type { MarketSortKey } from "@/types/api";

export function useMarkets(params: {
  category?: string;
  search?: string;
  sort?: MarketSortKey;
  limit?: number;
  offset?: number;
}) {
  const { category = "All", search = "", sort = "volume", limit = 50, offset = 0 } = params;
  return useQuery({
    queryKey: ["markets", category, search, sort, limit, offset],
    queryFn: () => api.markets({ category, search, sort, limit, offset }),
    // Keep the previous page on screen while the next one loads, so paging and
    // typing in the search box do not flash an empty table.
    placeholderData: keepPreviousData,
  });
}
