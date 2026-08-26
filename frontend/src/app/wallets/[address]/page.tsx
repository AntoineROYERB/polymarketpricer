"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { MetricCard } from "@/components/shared/metric-card";
import { DataTable } from "@/components/shared/data-table";
import { BarChart } from "@/components/charts/bar-chart";
import { SentimentBar } from "@/components/charts/sentiment-bar";

import { useWalletProfile, useWalletAlerts, useFollowList, useFollowWallet, useUnfollowWallet } from "@/hooks/use-alerts";
import { useAuth } from "@/lib/auth";
import type { Column } from "@/components/shared/data-table";
import type { AlertItem, WalletCategorySummary } from "@/types/api";

const alertColumns: Column<AlertItem>[] = [
  { key: "detected_at", label: "Time", align: "right", render: (r) => new Date(r.detected_at).toLocaleString() },
  { key: "market_question", label: "Market", render: (r) => (
    <a
      href={r.event_slug ? `https://polymarket.com/event/${r.event_slug}` : "#"}
      target={r.event_slug ? "_blank" : undefined}
      rel={r.event_slug ? "noopener noreferrer" : undefined}
      className="hover:text-accent-amber transition-colors block"
    >
      <span className="truncate block max-w-xs">{r.market_question}</span>
    </a>
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

type DataTab = "alerts" | "positions" | "edge";

export default function WalletProfilePage() {
  const params = useParams();
  const router = useRouter();
  const address = params.address as string;
  const { isAuthenticated } = useAuth();
  const { data: profile, isLoading } = useWalletProfile(address);
  const { data: alerts } = useWalletAlerts(address);
  const { data: follows } = useFollowList();
  const followWallet = useFollowWallet();
  const unfollowWallet = useUnfollowWallet();
  const [dataTab, setDataTab] = useState<DataTab>("alerts");
  const [error, setError] = useState<string | null>(null);

  const analytics = profile?.analytics;
  const specialistCategories = profile?.categories?.filter((c) => c.is_specialist) ?? [];
  const isFollowed = follows?.data?.some((f) => f.wallet === address) ?? false;

  const categoryData = (profile?.categories ?? []).map((c: WalletCategorySummary) => ({
    label: c.category,
    value: c.roi != null ? Number(c.roi) : 0,
  }));

  const handleFollow = () => {
    if (!isAuthenticated) { router.push("/login"); return; }
    setError(null);
    if (isFollowed) {
      unfollowWallet.mutate(address, {
        onError: (err) => setError(err.message),
      });
    } else {
      followWallet.mutate({ wallet: address }, {
        onError: (err) => setError(err.message),
      });
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-heading text-text-primary font-mono">{address.slice(0, 10)}...{address.slice(-6)}</h1>
            {error && (
              <div className="mt-2 bg-accent-rose/10 border border-accent-rose/30 rounded px-3 py-1.5 text-xs text-accent-rose">
                {error}
              </div>
            )}
            {specialistCategories.length > 0 && (
              <div className="flex gap-2 mt-2">
                {specialistCategories.map((cat) => (
                  <span key={cat.category} className="text-xs bg-accent-amber/10 text-accent-amber px-2 py-0.5 rounded">{cat.category}</span>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={handleFollow}
            disabled={followWallet.isPending || unfollowWallet.isPending}
            className={`px-4 py-2 text-xs rounded font-medium transition-colors ${
              isFollowed
                ? "bg-accent-rose/10 text-accent-rose border border-accent-rose/30 hover:bg-accent-rose/20"
                : "bg-accent-amber text-background hover:brightness-110"
            }`}
          >
            {isFollowed ? "Unfollow" : "Follow"}
          </button>
        </div>

        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="ROI" value={analytics?.roi != null ? `${Number(analytics.roi).toFixed(1)}%` : "-"} loading={isLoading} />
          <MetricCard label="Win Rate" value={analytics?.win_rate != null ? `${(Number(analytics.win_rate) * 100).toFixed(0)}%` : "-"} loading={isLoading} />
          <MetricCard label="PnL" value={`$${(Number(analytics?.total_pnl) || 0).toLocaleString()}`} loading={isLoading} trend={Number(analytics?.total_pnl) >= 0 ? "up" : "down"} />
          <MetricCard label="Volume" value={`$${(Number(analytics?.total_volume) || 0).toLocaleString()}`} loading={isLoading} />
        </div>

        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="Trades" value={analytics?.num_trades ?? "-"} loading={isLoading} />
          <MetricCard label="Profit Factor" value={analytics?.profit_factor?.toFixed(2) ?? "-"} loading={isLoading} />
          <MetricCard label="Avg Position" value={analytics?.avg_position_size ? `$${Number(analytics.avg_position_size).toFixed(0)}` : "-"} loading={isLoading} />
          <MetricCard label="Avg Hold" value={analytics?.avg_holding_duration ?? "-"} loading={isLoading} />
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div className="bg-surface border border-border rounded p-4 space-y-3">
            <h3 className="text-sm font-heading text-text-primary">Sentiment</h3>
            <SentimentBar buyPercent={65} />
          </div>

          {profile?.edge_metrics && (
            <div className="bg-surface border border-border rounded p-4 space-y-3">
              <h3 className="text-sm font-heading text-text-primary">Edge Metrics</h3>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-xs text-text-muted">Avg Edge</span>
                  <p className="text-text-primary font-mono text-lg">{profile.edge_metrics.avg_edge.toFixed(4)}</p>
                </div>
                <div>
                  <span className="text-xs text-text-muted">Edge Consistency</span>
                  <p className="text-text-primary font-mono text-lg">
                    {profile.edge_metrics.edge_consistency != null
                      ? `${(profile.edge_metrics.edge_consistency * 100).toFixed(0)}%`
                      : "-"}
                  </p>
                </div>
                <div>
                  <span className="text-xs text-text-muted">Edge Score</span>
                  <p className="text-text-primary font-mono text-lg">{profile.edge_metrics.edge_score?.toFixed(4) ?? "-"}</p>
                </div>
                <div>
                  <span className="text-xs text-text-muted">Edge Trades</span>
                  <p className="text-text-primary font-mono text-lg">{profile.edge_metrics.num_edge_trades}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {categoryData.length > 0 && (
          <div className="bg-surface border border-border rounded p-4 space-y-3">
            <h3 className="text-sm font-heading text-text-primary">Category Performance</h3>
            <BarChart data={categoryData} />
          </div>
        )}

        <div className="flex gap-1">
          {(["alerts", "positions", "edge"] as DataTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setDataTab(t)}
              className={`px-3 py-1.5 text-xs rounded transition-colors ${
                dataTab === t
                  ? "bg-accent-amber text-background font-medium"
                  : "bg-surface text-text-secondary hover:text-text-primary border border-border"
              }`}
            >
              {t === "alerts" ? "Recent Alerts" : t === "positions" ? "Current Positions" : "Edge History"}
            </button>
          ))}
        </div>

        {dataTab === "alerts" && (
          <DataTable
            columns={alertColumns}
            data={alerts?.data ?? []}
            keyExtractor={(r) => r.id}
          />
        )}

        {dataTab === "positions" && (
          <DataTable
            columns={[
              { key: "market_id", label: "Market", render: (r) => (
                <a
                  href={r.event_slug ? `https://polymarket.com/event/${r.event_slug}` : `/markets/${r.market_id}`}
                  target={r.event_slug ? "_blank" : undefined}
                  rel={r.event_slug ? "noopener noreferrer" : undefined}
                  className="hover:text-accent-amber transition-colors text-left block"
                >
                  <span className="truncate block max-w-xs">{r.question ?? r.market_id}</span>
                </a>
              )},
              { key: "side", label: "Side", render: (r) => (
                <span className={r.side === "BUY" ? "text-accent-emerald" : r.side === "SELL" ? "text-accent-rose" : ""}>
                  {r.side ?? "-"}
                </span>
              )},
              { key: "shares", label: "Shares", align: "right", render: (r) => r.shares },
              { key: "avg_entry_price", label: "Entry", align: "right", render: (r) => `$${Number(r.avg_entry_price).toFixed(4)}` },
              { key: "total_pnl", label: "PnL", align: "right", render: (r) => {
                const val = Number(r.total_pnl) || 0;
                return <span className={val >= 0 ? "text-accent-emerald" : "text-accent-rose"}>${Math.abs(val).toFixed(2)}</span>;
              }},
            ]}
            data={profile?.current_positions ?? []}
            keyExtractor={(r) => r.market_id}
          />
        )}

        {dataTab === "edge" && profile?.categories && (
          <div className="bg-surface border border-border rounded p-4 text-center">
            <p className="text-text-muted text-sm">Edge history per category available in a future release.</p>
          </div>
        )}
      </div>
    </AppShell>
  );
}
