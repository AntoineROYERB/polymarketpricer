"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { DataTable } from "@/components/shared/data-table";
import { WalletAddress } from "@/components/shared/wallet-address";
import { AnimatedCounter } from "@/components/shared/animated-counter";
import { useLeaderboardForTab } from "@/hooks/use-leaderboard";
import type { Column } from "@/components/shared/data-table";
import type { LeaderboardRow, LeaderboardTabType } from "@/types/api";

const CATEGORIES = ["All", "Politics", "Sports", "Crypto", "Economics", "Technology", "AI", "Geopolitics", "Entertainment"];

const TABS: { key: LeaderboardTabType; label: string }[] = [
  { key: "main", label: "Main" },
  { key: "emerging", label: "Emerging" },
  { key: "consistent", label: "Consistent" },
  { key: "edge", label: "Edge" },
  { key: "category", label: "By Category" },
];

export default function LeaderboardPage() {
  const router = useRouter();
  const [tab, setTab] = useState<LeaderboardTabType>("main");
  const [category, setCategory] = useState("All");
  const [offset, setOffset] = useState(0);
  const { data: rows, isLoading } = useLeaderboardForTab(tab, category, tab === "main" ? 100 : 50, offset);

  const isEdgeTab = tab === "edge";

  const columns: Column<LeaderboardRow>[] = [
    { key: "rank", label: "#", align: "right", render: (r) => r.rank as number },
    { key: "wallet", label: "Wallet", render: (r) => (
      <button onClick={() => router.push(`/wallets/${r.wallet}`)} className="hover:text-accent-amber transition-colors text-left">
        <WalletAddress address={r.wallet as string} />
      </button>
    )},
  ];

  if (isEdgeTab) {
    columns.push(
      { key: "edge_score", label: "Edge Score", align: "right", sortable: true, render: (r) => Number(r.edge_score || 0).toFixed(4) },
      { key: "avg_edge", label: "Avg Edge", align: "right", sortable: true, render: (r) => Number(r.avg_edge || 0).toFixed(4) },
      { key: "edge_consistency", label: "Consistency", align: "right", sortable: true, render: (r) => r.edge_consistency != null ? `${(Number(r.edge_consistency) * 100).toFixed(0)}%` : "-" },
      { key: "num_edge_trades", label: "Edge Trades", align: "right", sortable: true, render: (r) => String(r.num_edge_trades ?? 0) },
    );
  } else {
    columns.push(
      { key: "score", label: "Score", align: "right", sortable: true, render: (r) => Number(r.score || r.wallet_score || 0).toFixed(2) },
      { key: "roi", label: "ROI", align: "right", sortable: true, render: (r) => r.roi != null ? `${Number(r.roi).toFixed(1)}%` : "-" },
      { key: "win_rate", label: "Win Rate", align: "right", sortable: true, render: (r) => r.win_rate != null ? `${(Number(r.win_rate) * 100).toFixed(0)}%` : "-" },
      { key: "total_pnl", label: "PnL", align: "right", sortable: true, render: (r) => {
        const val = Number(r.total_pnl) || 0;
        return <span className={val >= 0 ? "text-accent-emerald" : "text-accent-rose"}>${Math.abs(val).toLocaleString()}</span>;
      }},
      { key: "num_trades", label: "Trades", align: "right", sortable: true, render: (r) => String(r.num_trades ?? 0) },
    );
    if (tab === "category") {
      columns.push({
        key: "total_volume", label: "Volume", align: "right", sortable: true,
        render: (r) => {
          const v = Number(r.total_volume) || 0;
          return v > 0 ? `$${v.toLocaleString()}` : "-";
        },
      });
    }
  }

  const top3 = rows.slice(0, 3);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-heading text-text-primary">Leaderboard</h1>
          {rows.length > 0 && !isEdgeTab && (
            <div className="flex items-center gap-2">
              <AnimatedCounter value={Number(rows[0].roi) || 0} suffix="%" className="text-lg text-accent-amber" />
              <span className="text-xs text-text-muted">top ROI</span>
            </div>
          )}
        </div>

        {top3.length === 3 && tab !== "category" && !isEdgeTab && (
          <div className="grid grid-cols-3 gap-4">
            {top3.map((row, i) => {
              const medalColors = ["text-accent-amber", "text-text-secondary", "text-accent-rose"];
              const borderColors = ["border-accent-amber", "border-text-muted", "border-accent-rose"];
              return (
                <button
                  key={row.wallet as string}
                  onClick={() => router.push(`/wallets/${row.wallet}`)}
                  className={`bg-surface border ${borderColors[i]} rounded p-4 space-y-2 hover:brightness-110 transition-all text-left`}
                >
                  <div className="flex items-center justify-between">
                    <span className={`text-2xl font-bold font-heading ${medalColors[i]}`}>#{row.rank}</span>
                    <WalletAddress address={row.wallet as string} />
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-text-muted text-xs">Score</span>
                      <p className="text-text-primary font-mono">{Number(row.score || 0).toFixed(2)}</p>
                    </div>
                    <div>
                      <span className="text-text-muted text-xs">ROI</span>
                      <p className="text-text-primary font-mono">{row.roi != null ? `${Number(row.roi).toFixed(1)}%` : "-"}</p>
                    </div>
                    <div>
                      <span className="text-text-muted text-xs">PnL</span>
                      <p className={(Number(row.total_pnl) || 0) >= 0 ? "text-accent-emerald font-mono" : "text-accent-rose font-mono"}>
                        ${Math.abs(Number(row.total_pnl) || 0).toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <span className="text-text-muted text-xs">Trades</span>
                      <p className="text-text-primary font-mono">{row.num_trades ?? 0}</p>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        <div className="flex gap-1 flex-wrap">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => { setTab(t.key); setOffset(0); }}
              className={`px-3 py-1.5 text-xs rounded transition-colors ${
                tab === t.key
                  ? "bg-accent-amber text-background font-medium"
                  : "bg-surface text-text-secondary hover:text-text-primary border border-border"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "category" && (
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
        )}

        <DataTable
          columns={columns}
          data={rows as LeaderboardRow[]}
          loading={isLoading}
          limit={tab === "main" ? 100 : 50}
          offset={offset}
          onOffsetChange={setOffset}
          keyExtractor={(r) => r.wallet as string}
        />
      </div>
    </AppShell>
  );
}
