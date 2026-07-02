"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { DataTable } from "@/components/shared/data-table";
import { AnimatedCounter } from "@/components/shared/animated-counter";
import { usePortfolio, usePortfolioPositions, usePortfolioTrades } from "@/hooks/use-alerts";
import type { Column } from "@/components/shared/data-table";
import type { PaperPositionResponse, PaperTradeResponse } from "@/types/api";

const positionColumns: Column<PaperPositionResponse>[] = [
  { key: "market_question", label: "Market", render: (r) => (
    <span className="truncate block max-w-xs">{r.market_question}</span>
  )},
  { key: "side", label: "Side", render: (r) => (
    <span className={r.side === "BUY" ? "text-accent-emerald" : "text-accent-rose"}>{r.side}</span>
  )},
  { key: "shares", label: "Shares", align: "right", render: (r) => r.shares },
  { key: "entry_price", label: "Entry", align: "right", render: (r) => `$${r.entry_price.toFixed(4)}` },
  { key: "current_price", label: "Current", align: "right", render: (r) => `$${r.current_price.toFixed(4)}` },
  { key: "unrealized_pnl", label: "Unrealized PnL", align: "right", render: (r) => {
    const val = r.unrealized_pnl;
    return <span className={val >= 0 ? "text-accent-emerald" : "text-accent-rose"}>${val.toFixed(2)}</span>;
  }},
];

const tradeColumns: Column<PaperTradeResponse>[] = [
  { key: "executed_at", label: "Date", align: "right", render: (r) => new Date(r.executed_at).toLocaleDateString() },
  { key: "market_question", label: "Market", render: (r) => (
    <span className="truncate block max-w-xs">{r.market_question}</span>
  )},
  { key: "side", label: "Side", render: (r) => (
    <span className={r.side === "BUY" ? "text-accent-emerald" : "text-accent-rose"}>{r.side}</span>
  )},
  { key: "shares", label: "Shares", align: "right", render: (r) => r.shares },
  { key: "price", label: "Price", align: "right", render: (r) => `$${r.price.toFixed(4)}` },
  { key: "amount_usd", label: "Amount", align: "right", render: (r) => `$${r.amount_usd.toFixed(2)}` },
  { key: "pnl", label: "PnL", align: "right", render: (r) => {
    const val = r.pnl;
    return <span className={val >= 0 ? "text-accent-emerald" : "text-accent-rose"}>${val.toFixed(2)}</span>;
  }},
];

export default function PortfolioPage() {
  const [tab, setTab] = useState<"positions" | "trades">("positions");
  const { data: portfolio, isLoading: loadingPortfolio } = usePortfolio();
  const { data: positions, isLoading: loadingPositions } = usePortfolioPositions();
  const { data: trades, isLoading: loadingTrades } = usePortfolioTrades();

  return (
    <AppShell>
      <div className="space-y-6">
        <h1 className="text-xl font-heading text-text-primary">Paper Portfolio</h1>

        <div className="grid grid-cols-4 gap-4">
          <MetricCard
            label="Balance"
            value={<AnimatedCounter value={portfolio?.current_balance ?? 0} prefix="$" decimals={2} />}
            loading={loadingPortfolio}
          />
          <MetricCard
            label="Total PnL"
            value={<AnimatedCounter value={portfolio?.total_pnl ?? 0} prefix="$" decimals={2} />}
            change={portfolio?.total_roi ?? 0}
            trend={(portfolio?.total_pnl ?? 0) >= 0 ? "up" : "down"}
            loading={loadingPortfolio}
          />
          <MetricCard
            label="Trades"
            value={portfolio?.total_trades ?? 0}
            loading={loadingPortfolio}
          />
          <MetricCard
            label="Volume"
            value={`$${(portfolio?.total_volume ?? 0).toLocaleString()}`}
            loading={loadingPortfolio}
          />
        </div>

        <div className="flex gap-1">
          <button
            onClick={() => setTab("positions")}
            className={`px-3 py-1.5 text-xs rounded transition-colors ${
              tab === "positions"
                ? "bg-accent-amber text-background font-medium"
                : "bg-surface text-text-secondary hover:text-text-primary border border-border"
            }`}
          >
            Positions
          </button>
          <button
            onClick={() => setTab("trades")}
            className={`px-3 py-1.5 text-xs rounded transition-colors ${
              tab === "trades"
                ? "bg-accent-amber text-background font-medium"
                : "bg-surface text-text-secondary hover:text-text-primary border border-border"
            }`}
          >
            Trade History
          </button>
        </div>

        {tab === "positions" ? (
          <DataTable
            columns={positionColumns}
            data={positions?.data ?? []}
            loading={loadingPositions}
            keyExtractor={(r) => r.id}
          />
        ) : (
          <DataTable
            columns={tradeColumns}
            data={trades?.data ?? []}
            loading={loadingTrades}
            keyExtractor={(r) => r.id}
          />
        )}
      </div>
    </AppShell>
  );
}
