"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { DataTable } from "@/components/shared/data-table";
import { WalletAddress } from "@/components/shared/wallet-address";
import { useFollowList, useFollowRecommendations } from "@/hooks/use-alerts";
import type { Column } from "@/components/shared/data-table";
import type { FollowResponse, FollowRecommendation } from "@/types/api";

type Tab = "followed" | "recommended";

const followedColumns: Column<FollowResponse>[] = [
  { key: "wallet", label: "Wallet", render: (r) => <WalletAddress address={r.wallet} /> },
  { key: "label", label: "Label", render: (r) => r.label || "-" },
  { key: "auto_copy_enabled", label: "Auto-Copy", render: (r) => r.auto_copy_enabled ? "ON" : "OFF" },
  { key: "copy_mode", label: "Mode", render: (r) => r.copy_mode || "-" },
  { key: "followed_at", label: "Followed", align: "right", render: (r) => new Date(r.followed_at).toLocaleDateString() },
];

const recColumns: Column<FollowRecommendation>[] = [
  { key: "wallet", label: "Wallet", render: (r) => <WalletAddress address={r.wallet} /> },
  { key: "follow_score", label: "Score", align: "right", render: (r) => r.follow_score.toFixed(2) },
  { key: "reasons", label: "Reasons", render: (r) => (
    <span className="text-xs text-text-secondary truncate block max-w-xs">{r.reasons.join(", ")}</span>
  )},
];

export default function FollowPage() {
  const [tab, setTab] = useState<Tab>("followed");
  const { data: follows, isLoading: loadingFollows } = useFollowList();
  const { data: recs, isLoading: loadingRecs } = useFollowRecommendations();

  return (
    <AppShell>
      <div className="space-y-6">
        <h1 className="text-xl font-heading text-text-primary">Follow Management</h1>

        <div className="flex gap-1">
          <button
            onClick={() => setTab("followed")}
            className={`px-3 py-1.5 text-xs rounded transition-colors ${
              tab === "followed"
                ? "bg-accent-amber text-background font-medium"
                : "bg-surface text-text-secondary hover:text-text-primary border border-border"
            }`}
          >
            Followed ({follows?.total ?? 0})
          </button>
          <button
            onClick={() => setTab("recommended")}
            className={`px-3 py-1.5 text-xs rounded transition-colors ${
              tab === "recommended"
                ? "bg-accent-amber text-background font-medium"
                : "bg-surface text-text-secondary hover:text-text-primary border border-border"
            }`}
          >
            Recommendations
          </button>
        </div>

        {tab === "followed" ? (
          <DataTable
            columns={followedColumns}
            data={follows?.data ?? []}
            loading={loadingFollows}
            keyExtractor={(r) => r.id}
          />
        ) : (
          <DataTable
            columns={recColumns}
            data={recs?.data ?? []}
            loading={loadingRecs}
            keyExtractor={(r) => r.wallet}
          />
        )}
      </div>
    </AppShell>
  );
}
