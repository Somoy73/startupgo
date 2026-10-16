import type { Scores } from "../api/types";
import { score } from "../lib/format";

export function Meter({ value, label, showValue = true }: { value: number; label: string; showValue?: boolean }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} aria-label={label} title={`${label}: ${score(value)} / 100`}>
      <div className="meter-track">
        <div className="meter-fill" style={{ width: `${pct}%` }} />
      </div>
      {showValue && <span className="meter-value">{score(value)}</span>}
    </div>
  );
}

export function BandBadge({ band }: { band: Scores["band"] }) {
  return (
    <span className={`badge band-${band}`}>
      <span className="dot" aria-hidden />
      {band}
    </span>
  );
}

export function LevelPill({ level, label }: { level: number; label: string }) {
  return (
    <span className="level-pill" title={`${label} level ${level} of 9`}>
      {level}
    </span>
  );
}

export function EvidenceDots({ level, label }: { level: number; label: string }) {
  return (
    <span className="evidence" aria-label={`Evidence ${level} of 4: ${label}`}>
      {[1, 2, 3, 4].map((i) => (
        <i key={i} className={i <= level ? "on" : ""} />
      ))}
      <span>{label}</span>
    </span>
  );
}
