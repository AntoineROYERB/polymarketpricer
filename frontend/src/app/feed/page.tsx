"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { DataTable } from "@/components/shared/data-table";
import { WalletAddress } from "@/components/shared/wallet-address";
import { useAlerts } from "@/hooks/use-alerts";
import { useWebSocket } from "@/hooks/use-websocket";
import type { Column } from "@/components/shared/data-table";
import type { AlertItem } from "@/types/api";

const CATEGORIES = ["All", "Politics", "Sports", "Crypto", "Economics", "Technology", "AI", "Geopolitics", "Entertainment"];

export default function FeedPage() {
  const router = useRouter();
  const columns: Column<AlertItem>[] = [
    { key: "detected_at", label: "Time", align: "right", render: (r) => new Date(r.detected_at).toLocaleString() },
    { key: "wallet", label: "Wallet", render: (r) => <WalletAddress address={r.wallet} /> },
    { key: "market_question", label: "Market", render: (r) => (
      <button onClick={() => r.market_id && router.push(`/markets/${r.market_id}`)} className="hover:text-accent-amber transition-colors text-left">
        <span className="text-text-primary max-w-xs truncate block">{r.market_question}</span>
      </button>
    )},
    { key: "action", label: "Action", render: (r) => {
      const isBuy = r.action.includes("NEW") || r.action.includes("INCREASE");
      return (
        <span className={isBuy ? "text-accent-emerald" : "text-accent-rose"}>
          {isBuy ? "BUY" : "SELL"}
        </span>
      );
    }},
    { key: "position_size", label: "Size", align: "right", render: (r) => `$${r.position_size.toLocaleString()}` },
    { key: "price", label: "Price", align: "right", render: (r) => `$${r.price.toFixed(4)}` },
    { key: "wallet_score", label: "Score", align: "right", render: (r) => r.wallet_score.toFixed(1) },
    { key: "category", label: "Category", render: (r) => (
      <span className="text-xs bg-surface-hover px-2 py-0.5 rounded">{r.category}</span>
    )},
  ];
  const [offset, setOffset] = useState(0);
  const [categoryFilter, setCategoryFilter] = useState("");
  const [minScoreFilter, setMinScoreFilter] = useState("");
  const [walletFilter, setWalletFilter] = useState("");
  const { data, isLoading } = useAlerts({
    limit: 50,
    offset,
    ...(categoryFilter ? { category: categoryFilter } : {}),
    ...(minScoreFilter ? { min_score: Number(minScoreFilter) } : {}),
    ...(walletFilter ? { wallet: walletFilter } : {}),
  });
  const { alerts: wsAlerts, status: wsStatus, connect, disconnect } = useWebSocket();
  const [liveMode, setLiveMode] = useState(false);

  useEffect(() => {
    if (liveMode) {
      connect();
    } else {
      disconnect();
    }
  }, [liveMode, connect, disconnect]);

  const mergedAlerts = [
    ...wsAlerts.map((wsa) => ({
      id: wsa.id,
      wallet: wsa.wallet,
      market_id: wsa.market_id,
      market_question: wsa.market_question,
      action: wsa.action,
      category: wsa.category,
      price: wsa.price,
      position_size: wsa.position_size,
      wallet_score: wsa.wallet_score,
      detected_at: new Date().toISOString(),
    })),
    ...(data?.data ?? []),
  ].slice(0, 100);

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-heading text-text-primary">Smart Money Feed</h1>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setLiveMode(!liveMode)}
              className={`flex items-center gap-2 px-3 py-1.5 text-xs rounded font-medium transition-colors ${
                liveMode
                  ? "bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/30"
                  : "bg-surface text-text-secondary border border-border hover:text-text-primary"
              }`}
            >
              {liveMode && (
                <span className={`w-2 h-2 rounded-full ${wsStatus === "connected" ? "bg-accent-emerald animate-pulse" : "bg-accent-amber"}`} />
              )}
              {liveMode ? (wsStatus === "connected" ? "LIVE" : wsStatus === "connecting" ? "Connecting..." : "Reconnect") : "Live"}
            </button>
            {liveMode && (
              <button
                onClick={disconnect}
                className="px-2 py-1 text-xs text-accent-rose hover:text-accent-rose/80 transition-colors"
              >
                Stop
              </button>
            )}
          </div>
        </div>

        <div className="flex gap-3 flex-wrap items-center">
          <select
            value={categoryFilter}
            onChange={(e) => { setCategoryFilter(e.target.value); setOffset(0); }}
            className="bg-surface border border-border rounded px-3 py-1.5 text-xs text-text-primary"
          >
            <option value="">All Categories</option>
            {CATEGORIES.filter((c) => c !== "All").map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
          <input
            type="number"
            placeholder="Min Score"
            value={minScoreFilter}
            onChange={(e) => { setMinScoreFilter(e.target.value); setOffset(0); }}
            className="bg-surface border border-border rounded px-3 py-1.5 text-xs text-text-primary w-24 font-mono"
            step="0.1"
            min="0"
            max="10"
          />
          <input
            type="text"
            placeholder="Wallet Address"
            value={walletFilter}
            onChange={(e) => { setWalletFilter(e.target.value); setOffset(0); }}
            className="bg-surface border border-border rounded px-3 py-1.5 text-xs text-text-primary w-48 font-mono"
          />
        </div>

        <DataTable
          columns={columns}
          data={mergedAlerts}
          loading={isLoading}
          limit={50}
          offset={offset}
          onOffsetChange={setOffset}
          keyExtractor={(r) => r.id}
        />
      </div>
    </AppShell>
  );
}
