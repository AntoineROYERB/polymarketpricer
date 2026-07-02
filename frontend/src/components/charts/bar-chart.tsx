"use client";

import { BarChart as RechartsBar, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

interface BarChartProps {
  data: { label: string; value: number }[];
  className?: string;
}

export function BarChart({ data, className }: BarChartProps) {
  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={200}>
        <RechartsBar data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "var(--color-text-muted)", fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius)",
              color: "var(--color-text-primary)",
              fontSize: 12,
            }}
          />
          <Bar dataKey="value" fill="var(--color-accent-amber)" radius={[2, 2, 0, 0]} />
        </RechartsBar>
      </ResponsiveContainer>
    </div>
  );
}
