import type { OceanKpiEvidence } from "../api/backend-types";
import { IconExternal } from "./Icons";

/** Ocean Impact Navigator KPIs the startup has evidence for, with the claim and its source. */
export function OceanImpact({ kpis }: { kpis: OceanKpiEvidence[] }) {
  const evidenced = kpis.filter((k) => k.evidence_level > 0);
  if (!evidenced.length) return <p className="muted">No impact evidence recorded.</p>;

  return (
    <div className="stack">
      {evidenced.map((k) => (
        <div key={k.kpi_code}>
          <div className="impact-row">
            <span>
              <strong>{k.kpi_code}</strong> · {k.kpi_name}
              <span className="muted"> ({k.area_name})</span>
            </span>
            <span className="chip" title={`Evidence level ${k.evidence_level} of 4`}>
              {k.evidence_label}
            </span>
          </div>
          {k.claim && (
            <p className="small muted">
              {k.claim}
              {k.source_url && (
                <>
                  {" "}
                  <a href={k.source_url} target="_blank" rel="noreferrer">
                    Source <IconExternal className="inline size-3" />
                  </a>
                </>
              )}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
