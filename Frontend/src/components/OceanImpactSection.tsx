import { useId, useState } from "react";
import type { OceanImpactArea, OceanKpiEvidence } from "../api/backend-types";
import { DetailsToggle } from "./DetailsToggle";
import { OceanAreaChart } from "./OceanAreaChart";
import { OceanImpact } from "./OceanImpact";

type Props = {
  kpis: OceanKpiEvidence[];
  /** Navigator areas A-F; the chart waits for them. */
  areas: OceanImpactArea[] | null;
};

/**
 * The Ocean impact box: evidence by Navigator area as a chart, with the area hints.
 * "Show details" expands every evidenced KPI with its claim and source.
 */
export function OceanImpactSection({ kpis, areas }: Props) {
  const [open, setOpen] = useState(false);
  const detailsId = useId();
  const evidenced = kpis.filter((k) => k.evidence_level > 0).length;

  return (
    <section className="card card-pad">
      <div className="card-head">
        <div>
          <h2>Ocean impact</h2>
          <span className="small muted">Ocean Impact Navigator · evidence 0–4</span>
        </div>
        {evidenced > 0 && (
          <DetailsToggle open={open} onToggle={() => setOpen((o) => !o)} controls={detailsId} />
        )}
      </div>
      {areas && <OceanAreaChart areas={areas} kpis={kpis} />}
      {evidenced === 0 ? (
        <p className="muted">No impact evidence recorded.</p>
      ) : (
        <div id={detailsId} hidden={!open} style={{ marginTop: 16 }}>
          <p className="small muted" style={{ marginBottom: 12 }}>
            {evidenced} KPI{evidenced === 1 ? "" : "s"} with evidence
          </p>
          <OceanImpact kpis={kpis} />
        </div>
      )}
    </section>
  );
}
