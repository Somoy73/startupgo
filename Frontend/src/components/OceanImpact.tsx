import type { OceanKpiEvidence } from "../api/types";
import { useAppData } from "../state/AppData";
import { IconExternal } from "./Icons";
import { EvidenceDots } from "./Scores";

/** Ocean Impact Navigator areas A-F with the startup's KPI evidence under each. */
export function OceanImpact({ kpis }: { kpis: OceanKpiEvidence[] }) {
  const { frameworks } = useAppData();
  return (
    <div className="areas">
      {(frameworks?.ocean_impact_areas ?? []).map((area) => {
        const items = kpis.filter((k) => k.area_code === area.code && k.evidence_level > 0);
        const best = Math.max(0, ...items.map((k) => k.evidence_level));
        return (
          <div className={`area${items.length ? "" : " off"}`} key={area.code}>
            <div className="area-head">
              <h3>
                <span className="area-code">{area.code}</span>
                {area.name}
              </h3>
              <span className="small muted">
                {items.length ? `${items.length} KPI${items.length > 1 ? "s" : ""} · best ${best}/4` : "Not addressed"}
              </span>
            </div>
            {items.map((k) => (
              <div className="kpi" key={k.kpi_code}>
                <span className="small">
                  <strong>{k.kpi_code}</strong> {k.kpi_name}
                </span>
                <EvidenceDots level={k.evidence_level} label={k.evidence_label} />
                <p className="claim">
                  {k.claim}{" "}
                  {k.source_url ? (
                    <a href={k.source_url} target="_blank" rel="noreferrer">
                      Source <IconExternal />
                    </a>
                  ) : (
                    <span className="muted">No source</span>
                  )}
                </p>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
