import { useId, useState } from "react";
import type { LevelDetail, Readiness, Scores } from "../api/backend-types";
import { rationalePoints, score } from "../lib/format";
import { Collapse } from "./Collapse";
import { CountUp } from "./CountUp";
import { DetailsToggle } from "./DetailsToggle";
import { ReadinessProfile } from "./ReadinessProfile";
import { ReadinessRadar } from "./ReadinessRadar";
import { Meter } from "./Scores";

type Props = { levels: LevelDetail[]; readiness: Readiness; scores: Scores };

/**
 * The Readiness profile box: the readiness index and the six KTH levels as a radar.
 * "Show details" expands what each level means, what the next one needs, and the rationale.
 */
export function ReadinessSection({ levels, readiness, scores }: Props) {
  const [open, setOpen] = useState(false);
  const detailsId = useId();
  const rationale = rationalePoints(readiness.rationale);

  return (
    <section className="card card-pad">
      <div className="card-head">
        <h2>Readiness profile</h2>
        <DetailsToggle open={open} onToggle={() => setOpen((o) => !o)} controls={detailsId} />
      </div>
      <div className="stat" style={{ padding: 0, marginBottom: 16 }}>
        <span className="label">Readiness index (KTH IRL)</span>
        <span className="value">
          <CountUp value={score(scores.readiness)} />
        </span>
        <Meter value={scores.readiness} label="Readiness index" showValue={false} />
        <span className="sub">
          TRL {readiness.trl} · BRL {readiness.brl} · spread {scores.readiness_spread}
        </span>
      </div>
      <ReadinessRadar levels={levels} lagging={scores.lagging_dimensions} />

      <Collapse open={open} id={detailsId} className="pt-4">
        <p className="small muted" style={{ marginBottom: 12 }}>
          KTH Innovation Readiness Level, 1–9
        </p>
        <ReadinessProfile levels={levels} lagging={scores.lagging_dimensions} />
        {rationale.length > 0 && (
          <div className="mt-4 border-t border-border pt-3">
            <h3 className="text-xs font-bold text-muted-foreground">Rationale</h3>
            <p className="small muted mb-1.5">
              {readiness.assessor} · {readiness.assessed_on.slice(0, 10)}
            </p>
            {rationale.length === 1 ? (
              <p className="small secondary">{rationale[0]}</p>
            ) : (
              <ul className="small secondary list-disc space-y-0.5 pl-4">
                {rationale.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Collapse>
    </section>
  );
}
