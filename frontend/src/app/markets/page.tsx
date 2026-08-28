"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { DataTable } from "@/components/shared/data-table";
import type { Column } from "@/components/shared/data-table";
import { useMarkets } from "@/hooks/use-markets";
import type { MarketSortKey, MarketSummary } from "@/types/api";

const CATEGORIES = ["All", "Politics", "Sports", "Crypto", "Economics", "Technology", "AI", "Geopolitics", "Entertainment"];

const SORTS: { key: MarketSortKey; label: string }[] = [
  { key: "volume", label: "Volume" },
  { key: "liquidity", label: "Liquidity" },
  { key: "recent", label: "Newest" },
];

const LIMIT = 50;

function formatUsd(value: number | null): string {
  if (!value) return "-";
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}k`;
  return `$${value.toFixed(0)}`;
}

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function MarketsPage() {
  const router = useRouter();
  const [category, setCategory] = useState("All");
  const [sort, setSort] = useState<MarketSortKey>("volume");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  // Debounce the search box so typing does not fire a request per keystroke.
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setOffset(0);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const { data, isLoading } = useMarkets({ category, search, sort, limit: LIMIT, offset });
  const rows = data?.data ?? [];
  const total = data?.total ?? 0;

  const columns: Column<MarketSummary>[] = [
    {
      key: "question",
      label: "Market",
      render: (m) => (
        <button
          onClick={() => router.push(`/markets/${m.id}`)}
          className="text-left hover:text-accent-amber transition-colors line-clamp-2"
        >
          {m.question}
        </button>
      ),
    },
    {
      key: "category",
      label: "Category",
      render: (m) =>
        m.category ? (
          <span className="text-xs px-2 py-0.5 rounded bg-surface-hover text-text-secondary">{m.category}</span>
        ) : (
          <span className="text-text-muted">-</span>
        ),
    },
    { key: "volume_usd", label: "Volume", align: "right", sortable: true, render: (m) => formatUsd(m.volume_usd) },
    { key: "liquidity_usd", label: "Liquidity", align: "right", sortable: true, render: (m) => formatUsd(m.liquidity_usd) },
    { key: "close_time", label: "Closes", align: "right", render: (m) => formatDate(m.close_time) },
  ];

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-heading text-text-primary">Markets</h1>
          <span className="text-xs text-text-muted">
            {total.toLocaleString()} ingested{search || category !== "All" ? " matching" : ""}
          </span>
        </div>

        <input
          type="search"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search markets..."
          className="w-full max-w-md bg-surface border border-border rounded px-3 py-2 text-sm text-text-primary placeholder:text-text-muted font-mono focus:outline-none focus:border-accent-amber"
        />

        <div className="flex gap-1 flex-wrap">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => { setCategory(cat); setOffset(0); }}
              className={`px-3 py-1.5 text-xs rounded transition-colors ${
                category === cat
                  ? "bg-accent-amber text-background font-medium"
                  : "bg-surface text-text-secondary hover:text-text-primary border border-border"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">Sort by</span>
          {SORTS.map((s) => (
            <button
              key={s.key}
              onClick={() => { setSort(s.key); setOffset(0); }}
              className={`px-3 py-1.5 text-xs rounded transition-colors ${
                sort === s.key
                  ? "bg-surface-hover text-text-primary border border-accent-amber"
                  : "bg-surface text-text-secondary hover:text-text-primary border border-border"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>

        {!isLoading && rows.length === 0 ? (
          <div className="bg-surface border border-border rounded p-8 text-center text-sm text-text-muted">
            No market matches these filters.
          </div>
        ) : (
          <DataTable
            columns={columns}
            data={rows}
            loading={isLoading && rows.length === 0}
            total={total}
            limit={LIMIT}
            offset={offset}
            onOffsetChange={setOffset}
            keyExtractor={(m) => m.id}
          />
        )}
      </div>
    </AppShell>
  );
}
