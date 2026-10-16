import type { Scores } from "../../api/types";
import { score } from "../../lib/format";
import { BandBadge, Meter } from "../Scores";

interface Props {
  preview: Scores | null;
  current: Scores | null;
  error: string | null;
}

function Delta({ next, prev }: { next: number; prev: number | undefined }) {
  if (prev === undefined) return null;
  const d = Math.round(next) - Math.round(prev);
  if (d === 0) return <span className="delta muted">±0</span>;
  return <span className={`delta ${d > 0 ? "up" : "down"}`}>{d > 0 ? `+${d}` : `−${-d}`}</span>;
}

const ROWS: { key: "readiness" | "ocean_impact" | "momentum"; label: string }[] = [
  { key: "readiness", label: "Readiness" },
  { key: "ocean_impact", label: "Ocean impact" },
  { key: "momentum", label: "Momentum" },
];

/** Live result of the scoring model for the assessment being edited, with change vs the saved one. */
export function ScorePreview({ preview, current, error }: Props) {
  return (
    <aside className="card card-pad score-preview" aria-live="polite">
      <h2>Live score</h2>
      {error && <p className="small error">{error}</p>}
      {!preview ? (
        <p className="small muted">Calculating…</p>
      ) : (
        <>
          <div className="row-gap" style={{ alignItems: "baseline", margin: "10px 0 4px" }}>
            <span className="hero-value">{score(preview.potential)}</span>
            <Delta next={preview.potential} prev={current?.potential} />
          </div>
          <div className="row-gap" style={{ marginBottom: 14 }}>
            <span className="small secondary">Investment potential</span>
            <BandBadge band={preview.band} />
          </div>
          {ROWS.map((r) => (
            <div className="preview-row" key={r.key}>
              <span className="small">{r.label}</span>
              <Meter value={preview[r.key]} label={r.label} />
              <Delta next={preview[r.key]} prev={current?.[r.key]} />
            </div>
          ))}
          {preview.imbalance_penalty > 0 && (
            <p className="small warn-text">
              −{preview.imbalance_penalty} imbalance penalty: readiness levels are {preview.readiness_spread} apart.
            </p>
          )}
          {preview.lagging_dimensions.length > 0 && (
            <p className="small warn-text">Lagging: {preview.lagging_dimensions.join(", ")}</p>
          )}
          <p className="small muted" style={{ marginTop: 10 }}>
            Ocean evidence: {preview.ocean_evidence_label}
            {preview.ocean_areas_covered.length > 0 && ` · areas ${preview.ocean_areas_covered.join(", ")}`}
          </p>
        </>
      )}
    </aside>
  );
}
