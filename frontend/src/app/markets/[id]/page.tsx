"use client";

import { useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";

import { DataTable } from "@/components/shared/data-table";
import { SentimentBar } from "@/components/charts/sentiment-bar";
import { WalletAddress } from "@/components/shared/wallet-address";
import { useMarketDetail } from "@/hooks/use-alerts";
import type { Column } from "@/components/shared/data-table";
import type { ActiveTraderEntry } from "@/types/api";

const buildTraderColumns = (
  onWalletClick: (wallet: string) => void,
): Column<ActiveTraderEntry>[] => [
  { key: "wallet", label: "Wallet", render: (r) => (
    <button onClick={() => onWalletClick(r.wallet)} className="hover:text-accent-amber transition-colors text-left">
      <WalletAddress address={r.wallet} />
    </button>
  )},
  { key: "side", label: "Side", render: (r) => (
    <span className={r.side === "BUY" ? "text-accent-emerald" : r.side === "SELL" ? "text-accent-rose" : ""}>{r.side ?? "-"}</span>
  )},
  { key: "position_size", label: "Size", align: "right", render: (r) => r.position_size != null ? `$${r.position_size.toLocaleString()}` : "-" },
  { key: "price", label: "Entry", align: "right", render: (r) => r.price != null ? `$${r.price.toFixed(4)}` : "-" },
  { key: "total_pnl", label: "PnL", align: "right", render: (r) => {
    if (r.total_pnl == null) return <span className="text-text-secondary">-</span>;
    return <span className={r.total_pnl >= 0 ? "text-accent-emerald" : "text-accent-rose"}>${Math.abs(r.total_pnl).toFixed(2)}</span>;
  }},
];

export default function MarketViewPage() {
  const params = useParams();
  const router = useRouter();
  const traderColumns = useMemo(
    () => buildTraderColumns((wallet) => router.push(`/wallets/${wallet}`)),
    [router],
  );
  const marketId = params.id as string;
  const { data: market, isLoading } = useMarketDetail(marketId);

  if (isLoading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <div className="h-8 w-64 bg-surface-hover rounded animate-pulse" />
          <div className="grid grid-cols-2 gap-6">
            {[1, 2].map((i) => (
              <div key={i} className="bg-surface border border-border rounded p-4 space-y-3 animate-pulse">
                <div className="h-4 w-24 bg-surface-hover rounded" />
                <div className="h-6 w-full bg-surface-hover rounded" />
              </div>
            ))}
          </div>
          <div className="bg-surface border border-border rounded p-4 space-y-3 animate-pulse">
            <div className="h-4 w-32 bg-surface-hover rounded" />
            <div className="h-40 bg-surface-hover rounded" />
          </div>
        </div>
      </AppShell>
    );
  }

  if (!market) {
    return (
      <AppShell>
        <div className="text-center py-12">
          <p className="text-text-muted">Market not found</p>
          <button onClick={() => router.push("/leaderboard")} className="text-accent-amber text-sm mt-2 hover:underline">
            Back to leaderboard
          </button>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-heading text-text-primary">{market.question}</h1>
            {market.category && (
              <span className="text-xs bg-surface-hover px-2 py-0.5 rounded text-text-secondary">{market.category}</span>
            )}
            {market.event_slug && (
              <a
                href={`https://polymarket.com/event/${market.event_slug}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-accent-amber hover:underline ml-auto"
              >
                View on Polymarket ↗
              </a>
            )}
          </div>
          <div className="flex gap-4 mt-2 text-xs text-text-muted font-mono">
            <span>ID: {market.id.slice(0, 8)}...</span>
            {market.condition_id && <span>Condition: {market.condition_id.slice(0, 8)}...</span>}
            {market.volume_usd != null && <span>Vol: ${market.volume_usd.toLocaleString()}</span>}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div className="bg-surface border border-border rounded p-4 space-y-3">
            <h3 className="text-sm font-heading text-text-primary">Sentiment</h3>
            <SentimentBar buyPercent={market.buy_percent} />
            <p className="text-xs text-text-muted mt-2">
              {market.buy_percent}% buyers / {Math.round(100 - market.buy_percent)}% sellers
              {market.outcomes.length > 0 && ` — ${market.outcomes.length} outcomes`}
            </p>
          </div>

          <div className="bg-surface border border-border rounded p-4 space-y-3">
            <h3 className="text-sm font-heading text-text-primary">Market Info</h3>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <span className="text-xs text-text-muted">Volume</span>
                <p className="text-text-primary font-mono">{market.volume_usd != null ? `$${market.volume_usd.toLocaleString()}` : "-"}</p>
              </div>
              <div>
                <span className="text-xs text-text-muted">Liquidity</span>
                <p className="text-text-primary font-mono">{market.liquidity_usd != null ? `$${market.liquidity_usd.toLocaleString()}` : "-"}</p>
              </div>
              <div>
                <span className="text-xs text-text-muted">Close</span>
                <p className="text-text-primary font-mono">{market.close_time ? new Date(market.close_time).toLocaleDateString() : "-"}</p>
              </div>
              <div>
                <span className="text-xs text-text-muted">Active Traders</span>
                <p className="text-text-primary font-mono">{market.active_traders.length}</p>
              </div>
            </div>
          </div>
        </div>

        {market.outcomes.length > 0 && (
          <div>
            <h3 className="text-sm font-heading text-text-primary mb-3">Outcomes</h3>
            <div className="grid grid-cols-2 gap-4">
              {market.outcomes.map((oc) => (
                <div key={oc.id} className={`bg-surface border ${oc.winner ? "border-accent-emerald" : "border-border"} rounded p-4`}>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-text-primary">{oc.label}</span>
                    {oc.winner && <span className="text-xs text-accent-emerald font-medium">WINNER</span>}
                  </div>
                  <p className="text-2xl font-heading font-mono mt-1">{oc.price != null ? `¢${(oc.price * 100).toFixed(1)}` : "-"}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="bg-surface border border-border rounded p-4 space-y-3">
          <h3 className="text-sm font-heading text-text-primary">Active Smart Money</h3>
          {market.active_traders.length > 0 ? (
            <DataTable
              columns={traderColumns}
              data={market.active_traders}
              keyExtractor={(r) => r.wallet}
            />
          ) : (
            <p className="text-text-muted text-sm py-4 text-center">No active traders detected yet.</p>
          )}
        </div>
      </div>
    </AppShell>
  );
}
