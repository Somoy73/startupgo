import { score } from "@/lib/format";

export function Meter({ value, label, showValue = true }: { value: number; label: string; showValue?: boolean }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      className="flex min-w-24 items-center gap-2"
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-label={label}
      title={`${label}: ${score(value)} / 100`}
    >
      <div className="h-2 flex-1 overflow-hidden rounded-sm bg-track">
        <div className="h-full rounded-r-sm bg-accent" style={{ width: `${pct}%` }} />
      </div>
      {showValue && <span className="min-w-[2ch] text-right text-md font-semibold tabular-nums">{score(value)}</span>}
    </div>
  );
}
