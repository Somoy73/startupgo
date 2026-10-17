import type { LevelDetail } from "../api/backend-types";

/** The six KTH IRL dimensions: current level, what it means, and what the next level needs. */
export function ReadinessProfile({
  levels,
  lagging,
}: {
  levels: LevelDetail[];
  lagging: string[];
}) {
  return (
    <div className="stack">
      {levels.map((l) => (
        <div key={l.dimension} className="readiness-row">
          <span>
            {l.dimension} · {l.name}
            {lagging.includes(l.dimension) && <span className="small error"> · lagging</span>}
          </span>
          <progress aria-label={`${l.name} readiness`} max={9} value={l.level} />
          <strong>{l.level}/9</strong>
          <span className="small">
            {l.summary}
            {l.next_summary && (
              <span className="muted">
                {" "}
                Next (L{l.level + 1}): {l.next_summary}
              </span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
