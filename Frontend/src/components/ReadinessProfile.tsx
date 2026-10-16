import type { LevelDetail } from "../api/types";

interface Props {
  levels: LevelDetail[];
  lagging: string[];
}

/** Six KTH IRL dimensions as segmented 1-9 bars, with the current and next level text. */
export function ReadinessProfile({ levels, lagging }: Props) {
  return (
    <div className="levels">
      <div className="level-scale" aria-hidden>
        <div />
        <div>
          {Array.from({ length: 9 }, (_, i) => (
            <span key={i}>{i + 1}</span>
          ))}
        </div>
      </div>
      {levels.map((l) => {
        const isLagging = lagging.includes(l.dimension);
        return (
          <div className="level-row" key={l.dimension}>
            <div className="dim">
              <strong>{l.dimension}</strong>
              <span>{l.name}</span>
            </div>
            <div
              className="level-track"
              role="img"
              aria-label={`${l.name} readiness level ${l.level} of 9${isLagging ? ", lagging" : ""}`}
              title={`${l.dimension} ${l.level}/9: ${l.summary}`}
            >
              {Array.from({ length: 9 }, (_, i) => (
                <div
                  key={i}
                  className={`cell${i < l.level ? " on" : ""}${i === l.level - 1 ? " end" : ""}${i < l.level && isLagging ? " lag" : ""}`}
                />
              ))}
            </div>
            <p className="level-text">
              <strong className="tabular">L{l.level}</strong> {l.summary}
              {isLagging && <strong> · Lagging: 3+ levels below the median</strong>}
              {l.next_summary && (
                <span className="next">
                  {" "}
                  Next (L{l.level + 1}): {l.next_summary}
                </span>
              )}
            </p>
          </div>
        );
      })}
    </div>
  );
}
