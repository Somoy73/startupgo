import { BAND_TONES, Chip } from "./Chip";
export function BandBadge({ band }: { band: string }) {
  return <Chip tone={BAND_TONES[band] ?? "neutral"}>{band}</Chip>;
}
export function LevelPill({ level, label }: { level: number; label: string }) {
  return (
    <span className="level-pill" title={`${label} ${level}/9`}>
      {level}
    </span>
  );
}
export function Meter({
  value,
  label,
  showValue = true,
}: {
  value: number;
  label: string;
  showValue?: boolean;
}) {
  return (
    <div className="meter">
      <Bar value={value} label={label} />
      {showValue && <strong>{Math.round(value)}</strong>}
    </div>
  );
}

/**
 * A progress bar whose fill grows in when it appears (styles.css, .bar-fill). Used in place of
 * <progress>, whose fill can't be animated; role="progressbar" keeps it readable to screen readers.
 */
export function Bar({ value, max = 100, label }: { value: number; max?: number; label: string }) {
  const percent = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div
      className="bar"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
    >
      <span className="bar-fill" style={{ width: `${percent}%` }} />
    </div>
  );
}
