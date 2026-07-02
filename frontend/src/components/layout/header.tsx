"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useWebSocket } from "@/hooks/use-websocket";

export function Header() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const { status, connect, disconnect } = useWebSocket();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (search.trim()) {
      router.push(`/wallets/${search.trim()}`);
    }
  };

  const wsColor = status === "connected" ? "text-accent-emerald" : status === "connecting" ? "text-accent-amber" : "text-accent-rose";

  return (
    <header className="flex items-center h-14 px-6 border-b border-border gap-4">
      <form onSubmit={handleSearch} className="flex-1 max-w-md">
        <input
          type="text"
          placeholder="Wallet address..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full bg-surface border border-border rounded px-3 py-1.5 text-sm font-mono text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-amber transition-colors"
        />
      </form>

      <div className="flex items-center gap-3 ml-auto">
        <button
          onClick={status === "connected" ? disconnect : connect}
          className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary transition-colors"
        >
          <span className={`text-lg ${wsColor}`}>●</span>
          {status === "connected" ? "Live" : status === "connecting" ? "Connecting..." : "Offline"}
        </button>
      </div>
    </header>
  );
}
