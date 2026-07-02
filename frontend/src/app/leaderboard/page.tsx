"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { DataTable } from "@/components/shared/data-table";
import { WalletAddress } from "@/components/shared/wallet-address";
import { AnimatedCounter } from "@/components/shared/animated-counter";
import { useLeaderboard, useCategoryLeaderboard } from "@/hooks/use-leaderboard";
import type { Column } from "@/components/shared/data-table";
import type { LeaderboardEntry, CategoryLeaderboardEntry } from "@/types/api";

const CATEGORIES = ["All", "Politics", "Sports", "Crypto", "Economics", "Technology", "AI", "Geopolitics", "Entertainment"];

type Row = (LeaderboardEntry | CategoryLeaderboardEntry) & { _score?: number };

export default function LeaderboardPage() {
  const [category, setCategory] = useState("All");
  const [offset, setOffset] = useState(0);
  const { data: allData, isLoading: loadingAll } = useLeaderboard(100, category === "All" ? offset : 0);
  const { data: catData, isLoading: loadingCat } = useCategoryLeaderboard(category, 50, category === "All" ? 0 : offset);

  const isLoading = category === "All" ? loadingAll : loadingCat;
  const rawData = category === "All" ? allData?.data : catData?.data;
  const rows: Row[] = (rawData ?? []).map((r) => ({
    ...r,
    _score: "score" in r ? r.score : ("wallet_score" in r ? r.wallet_score : 0) ?? 0,
  })) as Row[];

  const columns: Column<Row>[] = [
    { key: "rank", label: "#", align: "right", render: (r) => r.rank },
    { key: "wallet", label: "Wallet", render: (r) => <WalletAddress address={r.wallet} /> },
    { key: "score", label: "Score", align: "right", sortable: true, render: (r) => r._score?.toFixed(2) ?? "-" },
    { key: "roi", label: "ROI", align: "right", sortable: true, render: (r) => r.roi !== null ? `${Number(r.roi).toFixed(1)}%` : "-" },
    { key: "win_rate", label: "Win Rate", align: "right", sortable: true, render: (r) => r.win_rate !== null ? `${(Number(r.win_rate) * 100).toFixed(0)}%` : "-" },
    { key: "total_pnl", label: "PnL", align: "right", sortable: true, render: (r) => {
      const val = Number(r.total_pnl) || 0;
      return <span className={val >= 0 ? "text-accent-emerald" : "text-accent-rose"}>${Math.abs(val).toLocaleString()}</span>;
    }},
    { key: "num_trades", label: "Trades", align: "right", sortable: true, render: (r) => r.num_trades },
  ];

  if (category !== "All") {
    columns.push({
      key: "total_volume", label: "Volume", align: "right", sortable: true,
      render: (r) => {
        const v = Number((r as CategoryLeaderboardEntry).total_volume) || 0;
        return v > 0 ? `$${v.toLocaleString()}` : "-";
      },
    });
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-heading text-text-primary">Leaderboard</h1>
          {rows.length > 0 && (
            <div className="flex items-center gap-2">
              <AnimatedCounter value={Number(rows[0].roi) || 0} suffix="%" className="text-lg text-accent-amber" />
              <span className="text-xs text-text-muted">top ROI</span>
            </div>
          )}
        </div>

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

        <DataTable
          columns={columns}
          data={rows}
          loading={isLoading}
          limit={category === "All" ? 100 : 50}
          offset={offset}
          onOffsetChange={setOffset}
          keyExtractor={(r) => r.wallet}
        />
      </div>
    </AppShell>
  );
}
