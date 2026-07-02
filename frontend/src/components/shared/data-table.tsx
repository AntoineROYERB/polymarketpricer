"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  label: string;
  sortable?: boolean;
  align?: "left" | "right" | "center";
  render: (row: T) => React.ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  loading?: boolean;
  total?: number;
  limit?: number;
  offset?: number;
  onOffsetChange?: (offset: number) => void;
  keyExtractor: (row: T) => string;
}

export function DataTable<T>({
  columns,
  data,
  loading,
  total = 0,
  limit = 50,
  offset = 0,
  onOffsetChange,
  keyExtractor,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  if (loading) {
    return (
      <div className="bg-surface border border-border rounded overflow-hidden">
        <div className="grid grid-cols-4 gap-4 p-4 border-b border-border bg-surface-hover">
          {columns.map((col) => (
            <div key={col.key} className="h-3 w-24 bg-surface-hover rounded animate-pulse" />
          ))}
        </div>
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="grid grid-cols-4 gap-4 p-4 border-b border-border even:bg-[#0d0f12]">
            {columns.map((col) => (
              <div key={col.key} className={cn("h-4 rounded animate-pulse", i % 2 === 0 ? "bg-surface-hover" : "bg-surface")} />
            ))}
          </div>
        ))}
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="bg-surface border border-border rounded p-12 text-center">
        <p className="text-text-muted text-sm">No data</p>
      </div>
    );
  }

  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  return (
    <div className="bg-surface border border-border rounded overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-surface-hover">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3 text-xs uppercase tracking-wider text-text-muted font-sans",
                    col.sortable && "cursor-pointer hover:text-text-primary transition-colors",
                    col.align === "right" && "text-right",
                    col.align === "center" && "text-center",
                    !col.align && "text-left",
                  )}
                  onClick={() => col.sortable && handleSort(col.key)}
                >
                  <span className="flex items-center gap-1">
                    {col.label}
                    {col.sortable && sortKey === col.key && (
                      <span className="text-accent-amber text-xs">{sortDir === "asc" ? "↑" : "↓"}</span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr
                key={keyExtractor(row)}
                className="border-b border-border even:bg-[#0d0f12] hover:border-l-2 hover:border-l-accent-amber transition-all duration-150"
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      "px-4 py-3 text-sm",
                      col.align === "right" && "text-right font-mono tabular-nums",
                      col.align === "center" && "text-center",
                      !col.align && "text-left",
                    )}
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {onOffsetChange && total > limit && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-border">
          <span className="text-xs text-text-muted">
            {offset + 1}–{Math.min(offset + limit, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              disabled={!hasPrev}
              onClick={() => onOffsetChange(Math.max(0, offset - limit))}
              className="px-3 py-1 text-xs border border-border rounded disabled:opacity-30 hover:bg-surface-hover transition-colors"
            >
              Prev
            </button>
            <button
              disabled={!hasNext}
              onClick={() => onOffsetChange(offset + limit)}
              className="px-3 py-1 text-xs border border-border rounded disabled:opacity-30 hover:bg-surface-hover transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
