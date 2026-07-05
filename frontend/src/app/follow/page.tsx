"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { DataTable } from "@/components/shared/data-table";
import { WalletAddress } from "@/components/shared/wallet-address";
import { useFollowList, useFollowRecommendations, useFollowWallet, useUnfollowWallet, useUpdateFollow } from "@/hooks/use-alerts";
import { useAuth } from "@/lib/auth";
import type { Column } from "@/components/shared/data-table";
import type { FollowResponse, FollowRecommendation } from "@/types/api";

type Tab = "followed" | "recommended";

function EditModal({
  follow,
  onClose,
}: {
  follow: FollowResponse;
  onClose: () => void;
}) {
  const updateFollow = useUpdateFollow();
  const [label, setLabel] = useState(follow.label ?? "");
  const [autoCopy, setAutoCopy] = useState(follow.auto_copy_enabled);
  const [copyMode, setCopyMode] = useState(follow.copy_mode ?? "proportional");
  const [copyValue, setCopyValue] = useState(follow.copy_value.toString());

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-surface border border-border rounded-lg p-6 w-full max-w-md space-y-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-sm font-heading text-text-primary">Edit Follow</h2>
        <p className="text-xs text-text-muted font-mono">{follow.wallet.slice(0, 10)}...{follow.wallet.slice(-6)}</p>

        <div className="space-y-1">
          <label className="text-xs text-text-muted">Label</label>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="w-full bg-background border border-border rounded px-3 py-2 text-xs text-text-primary"
            placeholder="Optional label"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={autoCopy}
            onChange={(e) => setAutoCopy(e.target.checked)}
            id="auto-copy"
            className="accent-accent-amber"
          />
          <label htmlFor="auto-copy" className="text-xs text-text-primary">Auto-Copy Trades</label>
        </div>

        {autoCopy && (
          <>
            <div className="space-y-1">
              <label className="text-xs text-text-muted">Copy Mode</label>
              <select
                value={copyMode}
                onChange={(e) => setCopyMode(e.target.value)}
                className="w-full bg-background border border-border rounded px-3 py-2 text-xs text-text-primary"
              >
                <option value="proportional">Proportional</option>
                <option value="fixed">Fixed</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="text-xs text-text-muted">
                {copyMode === "proportional" ? "Allocation %" : "Fixed Amount ($)"}
              </label>
              <input
                type="number"
                value={copyValue}
                onChange={(e) => setCopyValue(e.target.value)}
                className="w-full bg-background border border-border rounded px-3 py-2 text-xs text-text-primary font-mono"
                step="0.01"
                min="0"
              />
            </div>
          </>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs bg-surface text-text-secondary border border-border rounded hover:text-text-primary transition-colors">
            Cancel
          </button>
          <button
            onClick={() => {
              updateFollow.mutate(
                { wallet: follow.wallet, label: label || undefined, auto_copy_enabled: autoCopy, copy_mode: copyMode as "proportional" | "fixed", copy_value: Number(copyValue) },
                { onSuccess: onClose },
              );
            }}
            disabled={updateFollow.isPending}
            className="px-3 py-1.5 text-xs bg-accent-amber text-background font-medium rounded hover:brightness-110 transition-colors"
          >
            {updateFollow.isPending ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ConfirmUnfollowModal({
  wallet,
  onConfirm,
  onClose,
}: {
  wallet: string;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-surface border border-border rounded-lg p-6 w-full max-w-sm space-y-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-sm font-heading text-text-primary">Unfollow Wallet</h2>
        <p className="text-xs text-text-muted font-mono">Unfollow {wallet.slice(0, 10)}...{wallet.slice(-6)}?</p>
        <p className="text-xs text-text-muted">Auto-copy trades will be disabled for this wallet.</p>
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs bg-surface text-text-secondary border border-border rounded hover:text-text-primary transition-colors">
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-3 py-1.5 text-xs bg-accent-rose text-white font-medium rounded hover:brightness-110 transition-colors"
          >
            Unfollow
          </button>
        </div>
      </div>
    </div>
  );
}

export default function FollowPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [tab, setTab] = useState<Tab>("followed");
  const { data: follows, isLoading: loadingFollows } = useFollowList();
  const { data: recs, isLoading: loadingRecs } = useFollowRecommendations();
  const followWallet = useFollowWallet();
  const unfollowWallet = useUnfollowWallet();
  const [editingWallet, setEditingWallet] = useState<string | null>(null);
  const [unfollowWalletAddr, setUnfollowWalletAddr] = useState<string | null>(null);

  if (!isAuthenticated) {
    return (
      <AppShell>
        <div className="text-center py-12 space-y-4">
          <p className="text-text-muted">Login to manage your followed wallets</p>
          <button
            onClick={() => router.push("/login")}
            className="px-4 py-2 text-sm bg-accent-amber text-background font-medium rounded hover:brightness-110 transition-colors"
          >
            Go to Login
          </button>
        </div>
      </AppShell>
    );
  }

  const editingFollow = editingWallet ? follows?.data?.find((f) => f.wallet === editingWallet) ?? null : null;

  const followedColumns: Column<FollowResponse>[] = [
    { key: "wallet", label: "Wallet", render: (r) => (
      <button onClick={() => router.push(`/wallets/${r.wallet}`)} className="hover:text-accent-amber transition-colors text-left">
        <WalletAddress address={r.wallet} />
      </button>
    )},
    { key: "label", label: "Label", render: (r) => r.label || "-" },
    { key: "auto_copy_enabled", label: "Auto-Copy", render: (r) => r.auto_copy_enabled ? "ON" : "OFF" },
    { key: "copy_mode", label: "Mode", render: (r) => r.copy_mode || "-" },
    { key: "followed_at", label: "Followed", align: "right", render: (r) => new Date(r.followed_at).toLocaleDateString() },
    { key: "actions", label: "", render: (r) => (
      <div className="flex gap-2">
        <button
          onClick={() => setEditingWallet(r.wallet)}
          className="text-xs text-accent-amber hover:underline"
        >
          Edit
        </button>
        <button
          onClick={() => setUnfollowWalletAddr(r.wallet)}
          className="text-xs text-accent-rose hover:underline"
        >
          Unfollow
        </button>
      </div>
    )},
  ];

  const recColumns: Column<FollowRecommendation>[] = [
    { key: "wallet", label: "Wallet", render: (r) => <WalletAddress address={r.wallet} /> },
    { key: "follow_score", label: "Score", align: "right", render: (r) => r.follow_score.toFixed(2) },
    { key: "reasons", label: "Reasons", render: (r) => (
      <span className="text-xs text-text-secondary truncate block max-w-xs">{r.reasons.join(", ")}</span>
    )},
    { key: "actions", label: "", render: (r) => (
      <button
        onClick={() => followWallet.mutate({ wallet: r.wallet })}
        disabled={followWallet.isPending}
        className="text-xs text-accent-amber hover:underline disabled:opacity-30"
      >
        Follow
      </button>
    )},
  ];

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

      {editingFollow && (
        <EditModal
          follow={editingFollow}
          onClose={() => setEditingWallet(null)}
        />
      )}

      {unfollowWalletAddr && (
        <ConfirmUnfollowModal
          wallet={unfollowWalletAddr}
          onConfirm={() => {
            unfollowWallet.mutate(unfollowWalletAddr);
            setUnfollowWalletAddr(null);
          }}
          onClose={() => setUnfollowWalletAddr(null)}
        />
      )}
    </AppShell>
  );
}
