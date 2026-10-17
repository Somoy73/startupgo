import { useId, useState } from "react";
import type { LevelDetail, Readiness, Scores } from "../api/backend-types";
import { score } from "../lib/format";
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

  return (
    <section className="card card-pad">
      <div className="card-head">
        <h2>Readiness profile</h2>
        <DetailsToggle open={open} onToggle={() => setOpen((o) => !o)} controls={detailsId} />
      </div>
      <div className="stat" style={{ padding: 0, marginBottom: 16 }}>
        <span className="label">Readiness index (KTH IRL)</span>
        <span className="value">{score(scores.readiness)}</span>
        <Meter value={scores.readiness} label="Readiness index" showValue={false} />
        <span className="sub">
          TRL {readiness.trl} · BRL {readiness.brl} · spread {scores.readiness_spread}
        </span>
      </div>
      <ReadinessRadar levels={levels} lagging={scores.lagging_dimensions} />

      <div id={detailsId} hidden={!open} style={{ marginTop: 16 }}>
        <p className="small muted" style={{ marginBottom: 12 }}>
          KTH Innovation Readiness Level, 1–9
        </p>
        <ReadinessProfile levels={levels} lagging={scores.lagging_dimensions} />
        {readiness.rationale && (
          <p className="small secondary" style={{ marginTop: 14 }}>
            {readiness.rationale}
          </p>
        )}
      </div>
    </section>
  );
}
