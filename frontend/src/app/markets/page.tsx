"use client";

import { AppShell } from "@/components/layout/app-shell";

export default function MarketsPage() {
  return (
    <AppShell>
      <div className="space-y-6">
        <h1 className="text-xl font-heading text-text-primary">Markets</h1>
        <p className="text-text-muted text-sm">Select a market from the smart money feed or search by ID to view detailed activity.</p>
      </div>
    </AppShell>
  );
}
