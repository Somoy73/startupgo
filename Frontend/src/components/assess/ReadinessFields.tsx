import type { DimensionKey, Frameworks, Levels } from "../../api/types";
import { Segmented } from "../Controls";

const LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 9];

interface Props {
  levels: Levels;
  dimensions: Frameworks["readiness_dimensions"];
  onChange: (key: DimensionKey, level: number) => void;
}

/** One 1-9 picker per KTH IRL dimension, showing the definition of the chosen and next level. */
export function ReadinessFields({ levels, dimensions, onChange }: Props) {
  return (
    <div className="assess-dims">
      {dimensions.map((d) => {
        const key = d.code.toLowerCase() as DimensionKey;
        const level = levels[key];
        const text = (n: number) => d.levels.find((l) => l.level === n)?.summary ?? "";
        return (
          <div className="assess-dim" key={d.code}>
            <div className="assess-dim-head">
              <div>
                <strong>{d.code}</strong> <span className="secondary">{d.name}</span>
              </div>
              <span className="small muted">weight {Math.round(d.weight * 100)}%</span>
            </div>
            <Segmented
              label={`${d.name} readiness level`}
              values={LEVELS}
              value={level}
              onChange={(n) => onChange(key, n)}
              describe={(n) => `L${n}: ${text(n)}`}
            />
            <p className="small">
              <strong>L{level}</strong> {text(level)}
            </p>
            {level < 9 && (
              <p className="small muted">
                To reach L{level + 1}: {text(level + 1)}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
