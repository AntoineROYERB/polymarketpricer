"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();
  const { setApiKey } = useAuth();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!key.trim()) {
      setError("API key is required");
      return;
    }
    setApiKey(key.trim());
    router.push("/leaderboard");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm bg-surface border border-border rounded p-8 space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-heading text-accent-amber tracking-wider">Edge Terminal</h1>
          <p className="text-sm text-text-muted">Enter your API key to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="password"
              placeholder="API Key"
              value={key}
              onChange={(e) => { setKey(e.target.value); setError(""); }}
              className="w-full bg-background border border-border rounded px-3 py-2 text-sm font-mono text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-amber transition-colors"
            />
            {error && <p className="text-xs text-accent-rose mt-1">{error}</p>}
          </div>

          <button
            type="submit"
            className="w-full bg-accent-amber text-background font-sans text-sm font-medium rounded py-2 hover:opacity-90 transition-opacity"
          >
            Connect
          </button>
        </form>

        <p className="text-xs text-text-muted text-center">
          Key is stored locally. Configure in Settings.
        </p>
      </div>
    </div>
  );
}
