import type { Frameworks, Scores } from "../api/backend-types";
import { score } from "../lib/format";
import { CountUp } from "./CountUp";

type Weights = Frameworks["potential_weights"];

const PARTS = [
  { key: "readiness", label: "Readiness", color: "bg-ocean" },
  { key: "ocean_impact", label: "Ocean impact", color: "bg-success" },
  { key: "momentum", label: "Momentum", color: "bg-amber-500" },
] as const;

const points = (n: number) => n.toFixed(1);

/**
 * How the investment potential is built: each score times its weight, stacked on a 0-100 bar.
 */
export function PotentialBreakdown({ scores, weights }: { scores: Scores; weights: Weights }) {
  const parts = PARTS.map((p) => ({ ...p, value: scores[p.key], weight: weights[p.key] })).map(
    (p) => ({ ...p, points: p.value * p.weight }),
  );

  return (
    <section className="card card-pad">
      <div className="card-head">
        <h2>How the potential is built</h2>
        <span className="small muted tabular">
          = <CountUp value={score(scores.potential)} /> / 100
        </span>
      </div>

      <div
        role="img"
        aria-label={`Investment potential ${score(scores.potential)}: ${parts
          .map((p) => `${p.label} ${points(p.points)}`)
          .join(", ")}`}
        className="relative flex h-6 w-full overflow-hidden rounded-full bg-wash"
      >
        {parts.map((p) => (
          <span key={p.key} className={p.color} style={{ width: `${p.points}%` }} />
        ))}
      </div>

      <dl className="mt-4 space-y-2 text-sm">
        {parts.map((p) => (
          <div key={p.key} className="flex items-center gap-2">
            <span aria-hidden className={`size-2.5 shrink-0 rounded-full ${p.color}`} />
            <dt className="flex-1">{p.label}</dt>
            <dd className="small muted tabular">
              {score(p.value)} × {p.weight.toFixed(2)} ={" "}
              <strong className="text-foreground">
                <CountUp value={p.points} decimals={1} />
              </strong>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
