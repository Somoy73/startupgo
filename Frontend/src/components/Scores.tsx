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
      <progress max={100} value={value} aria-label={label} />
      {showValue && <strong>{Math.round(value)}</strong>}
    </div>
  );
}
