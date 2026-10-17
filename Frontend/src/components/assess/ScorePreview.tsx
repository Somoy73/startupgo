import type { Scores } from "@/api/types";
import { score } from "@/lib/format";
import { BandBadge, card, cardPad, cx, Meter, row } from "@/components/ui";

interface Props {
  preview: Scores | null;
  current: Scores | null;
  error: string | null;
}

const DELTA = "text-right text-ctl font-semibold tabular-nums";
const WARN = "mt-2 border-l-3 border-warning pl-2 text-small text-fg-2";

function Delta({ next, prev }: { next: number; prev: number | undefined }) {
  if (prev === undefined) return null;
  const d = Math.round(next) - Math.round(prev);
  if (d === 0) return <span className={cx(DELTA, "text-muted")}>±0</span>;
  return <span className={cx(DELTA, d > 0 ? "text-good-ink" : "text-critical")}>{d > 0 ? `+${d}` : `−${-d}`}</span>;
}

const ROWS: { key: "readiness" | "ocean_impact" | "momentum"; label: string }[] = [
  { key: "readiness", label: "Readiness" },
  { key: "ocean_impact", label: "Ocean impact" },
  { key: "momentum", label: "Momentum" },
];

/** Live result of the scoring model for the assessment being edited, with change vs the saved one. */
export function ScorePreview({ preview, current, error }: Props) {
  return (
    <aside className={cx(card, cardPad)} aria-live="polite">
      <h2 className="mb-0.5">Live score</h2>
      {error && <p className="text-small text-critical">{error}</p>}
      {!preview ? (
        <p className="text-small text-muted">Calculating…</p>
      ) : (
        <>
          <div className="mt-2.5 mb-1 flex flex-wrap items-baseline gap-2">
            <span className="text-hero leading-none font-bold">{score(preview.potential)}</span>
            <Delta next={preview.potential} prev={current?.potential} />
          </div>
          <div className={cx(row, "mb-3.5")}>
            <span className="text-small text-fg-2">Investment potential</span>
            <BandBadge band={preview.band} />
          </div>
          {ROWS.map((r) => (
            <div className="grid grid-cols-[90px_1fr_36px] items-center gap-2 py-1" key={r.key}>
              <span className="text-small">{r.label}</span>
              <Meter value={preview[r.key]} label={r.label} />
              <Delta next={preview[r.key]} prev={current?.[r.key]} />
            </div>
          ))}
          {preview.imbalance_penalty > 0 && (
            <p className={WARN}>
              −{preview.imbalance_penalty} imbalance penalty: readiness levels are {preview.readiness_spread} apart.
            </p>
          )}
          {preview.lagging_dimensions.length > 0 && (
            <p className={WARN}>Lagging: {preview.lagging_dimensions.join(", ")}</p>
          )}
          <p className="mt-2.5 text-small text-muted">
            Ocean evidence: {preview.ocean_evidence_label}
            {preview.ocean_areas_covered.length > 0 && ` · areas ${preview.ocean_areas_covered.join(", ")}`}
          </p>
        </>
      )}
    </aside>
  );
}
