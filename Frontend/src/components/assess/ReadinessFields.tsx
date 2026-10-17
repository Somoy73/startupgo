import type { Levels, DimensionKey, Framework } from "../../api/types";
export function ReadinessFields({
  levels,
  dimensions,
  onChange,
}: {
  levels: Levels;
  dimensions: Framework["readiness_dimensions"];
  onChange: (key: DimensionKey, v: number) => void;
}) {
  return (
    <div className="stack">
      {dimensions.map((d) => (
        <label className="readiness-row" key={d.key}>
          <span>
            {d.code} · {d.name}
          </span>
          <input
            type="range"
            aria-label={d.name}
            min={1}
            max={9}
            value={levels[d.key]}
            onChange={(e) => onChange(d.key, Number(e.target.value))}
          />
          <strong>{levels[d.key]}/9</strong>
        </label>
      ))}
    </div>
  );
}
