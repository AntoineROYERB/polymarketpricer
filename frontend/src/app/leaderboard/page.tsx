"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { DataTable } from "@/components/shared/data-table";
import { WalletAddress } from "@/components/shared/wallet-address";
import { AnimatedCounter } from "@/components/shared/animated-counter";
import { useLeaderboard } from "@/hooks/use-leaderboard";
import type { Column } from "@/components/shared/data-table";
import type { LeaderEntry } from "@/types/api";

const CATEGORIES = ["All", "Politics", "Sports", "Crypto", "Science", "Pop Culture"];

const columns: Column<LeaderEntry>[] = [
  { key: "wallet", label: "Wallet", render: (r) => <WalletAddress address={r.wallet} /> },
  { key: "roi", label: "ROI", align: "right", sortable: true, render: (r) => `${r.roi.toFixed(1)}%` },
  { key: "win_rate", label: "Win Rate", align: "right", sortable: true, render: (r) => `${(r.win_rate * 100).toFixed(0)}%` },
  { key: "total_pnl", label: "PnL", align: "right", sortable: true, render: (r) => {
    const val = r.total_pnl;
    return <span className={val >= 0 ? "text-accent-emerald" : "text-accent-rose"}>${Math.abs(val).toLocaleString()}</span>;
  }},
  { key: "total_volume", label: "Volume", align: "right", sortable: true, render: (r) => `$${r.total_volume.toLocaleString()}` },
  { key: "num_trades", label: "Trades", align: "right", sortable: true, render: (r) => r.num_trades },
  { key: "profit_factor", label: "Profit Factor", align: "right", sortable: true, render: (r) => r.profit_factor.toFixed(2) },
];

export default function LeaderboardPage() {
  const [category, setCategory] = useState("All");
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useLeaderboard(category, 50, offset);

  const topRoi = data?.data?.[0]?.roi ?? 0;

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-heading text-text-primary">Leaderboard</h1>
          <div className="flex items-center gap-2">
            <AnimatedCounter value={topRoi} suffix="%" className="text-lg text-accent-amber" />
            <span className="text-xs text-text-muted">top ROI</span>
          </div>
        </div>

        <div className="flex gap-1">
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
          data={data?.data ?? []}
          loading={isLoading}
          total={data?.data?.length}
          limit={50}
          offset={offset}
          onOffsetChange={setOffset}
          keyExtractor={(r) => r.wallet}
        />
      </div>
    </AppShell>
  );
}
