import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  change?: number;
  icon?: ReactNode;
  trend?: "up" | "down" | "neutral";
  loading?: boolean;
  className?: string;
}

export function MetricCard({ label, value, change, icon, trend, loading, className }: MetricCardProps) {
  if (loading) {
    return (
      <div className={cn("bg-surface border border-border rounded p-4 space-y-2 animate-pulse", className)}>
        <div className="h-3 w-20 bg-surface-hover rounded" />
        <div className="h-7 w-32 bg-surface-hover rounded" />
      </div>
    );
  }

  const changeColor = trend === "up" ? "text-accent-emerald" : trend === "down" ? "text-accent-rose" : "text-text-muted";

  return (
    <div className={cn("bg-surface border border-border rounded p-4 hover:border-accent-amber/30 transition-colors", className)}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs uppercase tracking-wider text-text-muted font-sans">{label}</span>
        {icon && <span className="text-text-muted">{icon}</span>}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-heading text-text-primary">{value}</span>
        {change !== undefined && (
          <span className={cn("text-sm font-mono", changeColor)}>
            {change > 0 ? "+" : ""}{change}%
          </span>
        )}
      </div>
    </div>
  );
}
