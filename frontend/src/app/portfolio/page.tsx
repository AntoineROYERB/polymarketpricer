"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { DataTable } from "@/components/shared/data-table";
import { AnimatedCounter } from "@/components/shared/animated-counter";
import { usePortfolio, usePortfolioPositions, usePortfolioTrades, useClosePosition, useResetPortfolio } from "@/hooks/use-alerts";
import type { Column } from "@/components/shared/data-table";
import type { PaperPositionResponse, PaperTradeResponse } from "@/types/api";

function ConfirmModal({
  title,
  message,
  confirmLabel,
  onConfirm,
  onClose,
  danger,
}: {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onClose: () => void;
  danger?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-surface border border-border rounded-lg p-6 w-full max-w-sm space-y-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-sm font-heading text-text-primary">{title}</h2>
        <p className="text-xs text-text-muted">{message}</p>
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs bg-surface text-text-secondary border border-border rounded hover:text-text-primary transition-colors">
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-3 py-1.5 text-xs font-medium rounded hover:brightness-110 transition-colors ${
              danger ? "bg-accent-rose text-white" : "bg-accent-amber text-background"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PortfolioPage() {
  const [tab, setTab] = useState<"positions" | "trades">("positions");
  const [closingPositionId, setClosingPositionId] = useState<string | null>(null);
  const [showResetModal, setShowResetModal] = useState(false);
  const { data: portfolio, isLoading: loadingPortfolio } = usePortfolio();
  const { data: positions, isLoading: loadingPositions } = usePortfolioPositions();
  const { data: trades, isLoading: loadingTrades } = usePortfolioTrades();
  const closePosition = useClosePosition();
  const resetPortfolio = useResetPortfolio();

  const positionColumns: Column<PaperPositionResponse>[] = [
    { key: "market_id", label: "Market", render: (r) => (
      <a
        href={r.event_slug ? `https://polymarket.com/event/${r.event_slug}` : "#"}
        target={r.event_slug ? "_blank" : undefined}
        rel={r.event_slug ? "noopener noreferrer" : undefined}
        className="hover:text-accent-amber transition-colors block"
      >
        <span className="truncate block max-w-xs">{r.market_id}</span>
      </a>
    )},
    { key: "side", label: "Side", render: (r) => (
      <span className={r.side === "BUY" ? "text-accent-emerald" : "text-accent-rose"}>{r.side}</span>
    )},
    { key: "shares", label: "Shares", align: "right", render: (r) => r.shares },
    { key: "avg_entry_price", label: "Entry", align: "right", render: (r) => `$${r.avg_entry_price.toFixed(4)}` },
    { key: "current_price", label: "Current", align: "right", render: (r) => r.current_price != null ? `$${r.current_price.toFixed(4)}` : "—" },
    { key: "unrealized_pnl", label: "Unrealized PnL", align: "right", render: (r) => {
      const val = r.unrealized_pnl;
      if (val == null) return <span className="text-text-secondary">—</span>;
      return <span className={val >= 0 ? "text-accent-emerald" : "text-accent-rose"}>${val.toFixed(2)}</span>;
    }},
    {
      key: "pnl_pct", label: "PnL %", align: "right", render: (r) => {
        const cost = r.cost_basis;
        const pnl = r.unrealized_pnl ?? r.realized_pnl ?? 0;
        if (!cost) return <span className="text-text-secondary">—</span>;
        const pct = (pnl / cost) * 100;
        return <span className={pnl >= 0 ? "text-accent-emerald" : "text-accent-rose"}>{pct >= 0 ? "+" : ""}{pct.toFixed(1)}%</span>;
      },
    },
    { key: "actions", label: "", render: (r) =>
      r.status === "OPEN" ? (
        <button
          onClick={() => setClosingPositionId(r.id)}
          className="text-xs text-accent-rose hover:underline"
        >
          Close
        </button>
      ) : null,
    },
  ];

  const tradeColumns: Column<PaperTradeResponse>[] = [
    { key: "executed_at", label: "Date", align: "right", render: (r) => new Date(r.executed_at).toLocaleDateString() },
    { key: "market_id", label: "Market", render: (r) => (
      <a
        href={r.event_slug ? `https://polymarket.com/event/${r.event_slug}` : "#"}
        target={r.event_slug ? "_blank" : undefined}
        rel={r.event_slug ? "noopener noreferrer" : undefined}
        className="hover:text-accent-amber transition-colors block"
      >
        <span className="truncate block max-w-xs">{r.market_id}</span>
      </a>
    )},
    { key: "side", label: "Side", render: (r) => (
      <span className={r.side === "BUY" ? "text-accent-emerald" : "text-accent-rose"}>{r.side}</span>
    )},
    { key: "shares", label: "Shares", align: "right", render: (r) => r.shares },
    { key: "price", label: "Price", align: "right", render: (r) => `$${r.price.toFixed(4)}` },
    { key: "amount_usd", label: "Amount", align: "right", render: (r) => `$${r.amount_usd.toFixed(2)}` },
  ];

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-heading text-text-primary">Paper Portfolio</h1>
          <button
            onClick={() => setShowResetModal(true)}
            className="px-3 py-1.5 text-xs text-accent-rose border border-accent-rose/30 rounded hover:bg-accent-rose/10 transition-colors"
          >
            Reset Portfolio
          </button>
        </div>

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
            total={positions?.total}
            keyExtractor={(r) => r.id}
          />
        ) : (
          <DataTable
            columns={tradeColumns}
            data={trades?.data ?? []}
            loading={loadingTrades}
            total={trades?.total}
            keyExtractor={(r) => r.id}
          />
        )}
      </div>

      {closingPositionId && (
        <ConfirmModal
          title="Close Position"
          message="Are you sure you want to close this position? This will realize any PnL."
          confirmLabel="Close"
          onConfirm={() => {
            closePosition.mutate(closingPositionId);
            setClosingPositionId(null);
          }}
          onClose={() => setClosingPositionId(null)}
        />
      )}

      {showResetModal && (
        <ConfirmModal
          title="Reset Portfolio"
          message="This will close all positions and reset your balance to $10,000. This cannot be undone."
          confirmLabel="Reset"
          danger
          onConfirm={() => {
            resetPortfolio.mutate(10000);
            setShowResetModal(false);
          }}
          onClose={() => setShowResetModal(false)}
        />
      )}
    </AppShell>
  );
}
