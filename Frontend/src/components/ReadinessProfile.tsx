import { DIMENSIONS, type Levels, type DimensionKey } from "../api/types";
export function ReadinessProfile({ levels, lagging }: { levels: Levels; lagging: DimensionKey[] }) {
  return (
    <div className="stack">
      {DIMENSIONS.map((d) => (
        <div key={d.key} className="readiness-row">
          <span>
            {d.code} · {d.name}
          </span>
          <progress aria-label={d.name} max={9} value={levels[d.key]} />
          <strong>{levels[d.key]}/9</strong>
          {lagging.includes(d.key) && <span className="small muted">Lagging</span>}
        </div>
      ))}
    </div>
  );
}
