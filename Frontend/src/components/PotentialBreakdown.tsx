import type { Frameworks, Scores } from "../api/backend-types";
import { score } from "../lib/format";

type Weights = Frameworks["potential_weights"];

const PARTS = [
  { key: "readiness", label: "Readiness", color: "bg-ocean" },
  { key: "ocean_impact", label: "Ocean impact", color: "bg-success" },
  { key: "momentum", label: "Momentum", color: "bg-amber-500" },
] as const;

const points = (n: number) => n.toFixed(1);

/**
 * How the investment potential is built: each score times its weight, stacked on a 0-100 bar,
 * minus the imbalance penalty (struck through at the end of the stack).
 */
export function PotentialBreakdown({ scores, weights }: { scores: Scores; weights: Weights }) {
  const parts = PARTS.map((p) => ({ ...p, value: scores[p.key], weight: weights[p.key] })).map(
    (p) => ({ ...p, points: p.value * p.weight }),
  );
  const penalty = scores.imbalance_penalty;
  const blended = parts.reduce((sum, p) => sum + p.points, 0);
  // The penalty eats into the end of the stack, so the solid part ends at the potential.
  let left = Math.max(0, blended - penalty);

  return (
    <section className="card card-pad">
      <div className="card-head">
        <h2>How the potential is built</h2>
        <span className="small muted tabular">= {score(scores.potential)} / 100</span>
      </div>

      <div
        role="img"
        aria-label={`Investment potential ${score(scores.potential)}: ${parts
          .map((p) => `${p.label} ${points(p.points)}`)
          .join(", ")}${penalty > 0 ? `, minus imbalance penalty ${points(penalty)}` : ""}`}
        className="relative flex h-6 w-full overflow-hidden rounded-full bg-wash"
      >
        {parts.map((p) => {
          const solid = Math.min(p.points, left);
          left -= solid;
          const struck = p.points - solid;
          return [
            <span key={p.key} className={p.color} style={{ width: `${solid}%` }} />,
            struck > 0 && (
              <span
                key={`${p.key}-penalty`}
                className="penalty-stripes"
                style={{ width: `${struck}%` }}
              />
            ),
          ];
        })}
      </div>

      <dl className="mt-4 grid gap-2 text-sm">
        {parts.map((p) => (
          <div key={p.key} className="flex items-center gap-2">
            <span aria-hidden className={`size-2.5 shrink-0 rounded-full ${p.color}`} />
            <dt className="flex-1">{p.label}</dt>
            <dd className="small muted tabular">
              {score(p.value)} × {p.weight.toFixed(2)} ={" "}
              <strong className="text-foreground">{points(p.points)}</strong>
            </dd>
          </div>
        ))}
        {penalty > 0 && (
          <div className="flex items-center gap-2">
            <span aria-hidden className="penalty-stripes size-2.5 shrink-0 rounded-full" />
            <dt className="flex-1">
              Imbalance penalty
              <span className="small muted"> (readiness spread {scores.readiness_spread})</span>
            </dt>
            <dd className="small tabular text-destructive">
              <strong>−{points(penalty)}</strong>
            </dd>
          </div>
        )}
      </dl>
    </section>
  );
}
