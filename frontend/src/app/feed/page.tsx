"use client";

import { useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { DataTable } from "@/components/shared/data-table";
import { WalletAddress } from "@/components/shared/wallet-address";
import { useAlerts } from "@/hooks/use-alerts";
import type { Column } from "@/components/shared/data-table";
import type { AlertItem } from "@/types/api";

const columns: Column<AlertItem>[] = [
  { key: "detected_at", label: "Time", align: "right", render: (r) => new Date(r.detected_at).toLocaleString() },
  { key: "wallet", label: "Wallet", render: (r) => <WalletAddress address={r.wallet} /> },
  { key: "market_question", label: "Market", render: (r) => (
    <span className="text-text-primary max-w-xs truncate block">{r.market_question}</span>
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

export default function FeedPage() {
  const [offset, setOffset] = useState(0);
  const { data, isLoading } = useAlerts({ limit: 50, offset });

  return (
    <AppShell>
      <div className="space-y-6">
        <h1 className="text-xl font-heading text-text-primary">Smart Money Feed</h1>
        <DataTable
          columns={columns}
          data={data?.data ?? []}
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
