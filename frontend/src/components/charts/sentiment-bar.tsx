interface SentimentBarProps {
  buyPercent: number;
  className?: string;
}

export function SentimentBar({ buyPercent, className }: SentimentBarProps) {
  const sellPercent = 100 - buyPercent;
  return (
    <div className={`space-y-1 ${className ?? ""}`}>
      <div className="flex justify-between text-xs font-mono">
        <span className="text-accent-emerald">{Math.round(buyPercent)}% Bullish</span>
        <span className="text-accent-rose">{Math.round(sellPercent)}% Bearish</span>
      </div>
      <div className="relative h-2 bg-border rounded overflow-hidden border border-border">
        <div
          className="absolute inset-y-0 left-0 bg-accent-emerald transition-all duration-500"
          style={{ width: `${buyPercent}%` }}
        />
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-accent-amber/50" />
      </div>
    </div>
  );
}
