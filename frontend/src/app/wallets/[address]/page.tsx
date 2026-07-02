"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { DataTable } from "@/components/shared/data-table";
import { SentimentBar } from "@/components/charts/sentiment-bar";
import { useWalletProfile, useWalletAlerts } from "@/hooks/use-alerts";
import type { Column } from "@/components/shared/data-table";
import type { AlertItem } from "@/types/api";

const alertColumns: Column<AlertItem>[] = [
  { key: "detected_at", label: "Time", align: "right", render: (r) => new Date(r.detected_at).toLocaleString() },
  { key: "market_question", label: "Market", render: (r) => (
    <span className="truncate block max-w-xs">{r.market_question}</span>
  )},
  { key: "action", label: "Action", render: (r) => {
    const isBuy = r.action.includes("NEW") || r.action.includes("INCREASE");
    return <span className={isBuy ? "text-accent-emerald" : "text-accent-rose"}>{isBuy ? "BUY" : "SELL"}</span>;
  }},
  { key: "position_size", label: "Size", align: "right", render: (r) => `$${r.position_size.toLocaleString()}` },
  { key: "price", label: "Price", align: "right", render: (r) => `$${r.price.toFixed(4)}` },
  { key: "category", label: "Category", render: (r) => (
    <span className="text-xs bg-surface-hover px-2 py-0.5 rounded">{r.category}</span>
  )},
];

export default function WalletProfilePage() {
  const params = useParams();
  const address = params.address as string;
  const { data: profile, isLoading } = useWalletProfile(address);
  const { data: alerts } = useWalletAlerts(address);

  return (
    <AppShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-xl font-heading text-text-primary font-mono">{address.slice(0, 10)}...{address.slice(-6)}</h1>
          {profile?.specialist_categories && (
            <div className="flex gap-2 mt-2">
              {profile.specialist_categories.map((cat) => (
                <span key={cat} className="text-xs bg-accent-amber/10 text-accent-amber px-2 py-0.5 rounded">{cat}</span>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="ROI" value={profile ? `${profile.roi.toFixed(1)}%` : "-"} loading={isLoading} />
          <MetricCard label="Win Rate" value={profile ? `${(profile.win_rate * 100).toFixed(0)}%` : "-"} loading={isLoading} />
          <MetricCard label="PnL" value={profile ? `$${profile.total_pnl.toLocaleString()}` : "-"} loading={isLoading} trend={profile?.total_pnl && profile.total_pnl >= 0 ? "up" : "down"} />
          <MetricCard label="Volume" value={profile ? `$${profile.total_volume.toLocaleString()}` : "-"} loading={isLoading} />
        </div>

        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="Trades" value={profile?.total_trades ?? "-"} loading={isLoading} />
          <MetricCard label="Profit Factor" value={profile?.profit_factor.toFixed(2) ?? "-"} loading={isLoading} />
          <MetricCard label="Avg Position" value={profile ? `$${profile.avg_position_size.toFixed(0)}` : "-"} loading={isLoading} />
          <MetricCard label="Avg Hold" value={profile?.avg_holding_duration ?? "-"} loading={isLoading} />
        </div>

        <div className="bg-surface border border-border rounded p-4">
          <h3 className="text-sm font-heading text-text-primary mb-3">Sentiment</h3>
          <SentimentBar buyPercent={65} />
        </div>

        <div>
          <h3 className="text-sm font-heading text-text-primary mb-3">Recent Alerts</h3>
          <DataTable
            columns={alertColumns}
            data={alerts?.data ?? []}
            keyExtractor={(r) => r.id}
          />
        </div>
      </div>
    </AppShell>
  );
}
