"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { SentimentBar } from "@/components/charts/sentiment-bar";

export default function MarketViewPage() {
  const params = useParams();
  const marketId = params.id as string;

  return (
    <AppShell>
      <div className="space-y-6">
        <h1 className="text-xl font-heading text-text-primary font-mono">Market {marketId.slice(0, 8)}...</h1>

        <div className="grid grid-cols-2 gap-6">
          <div className="bg-surface border border-border rounded p-4 space-y-3">
            <h3 className="text-sm font-heading text-text-primary">Sentiment</h3>
            <SentimentBar buyPercent={58} />
          </div>

          <div className="bg-surface border border-border rounded p-4 space-y-3">
            <h3 className="text-sm font-heading text-text-primary">Active Smart Money</h3>
            <p className="text-text-muted text-sm">No active traders detected yet.</p>
          </div>
        </div>

        <div className="bg-surface border border-border rounded p-4 space-y-3">
          <h3 className="text-sm font-heading text-text-primary">Recent Activity</h3>
          <p className="text-text-muted text-sm">No activity logged for this market.</p>
        </div>
      </div>
    </AppShell>
  );
}
