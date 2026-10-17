import { LuExternalLink } from "react-icons/lu";
import type { OceanKpiEvidence } from "@/api/types";
import { useAppData } from "@/state/AppData";
import { areaCode, cx, EvidenceDots } from "@/components/ui";

/** Ocean Impact Navigator areas A-F with the startup's KPI evidence under each. */
export function OceanImpact({ kpis }: { kpis: OceanKpiEvidence[] }) {
  const { frameworks } = useAppData();
  return (
    <div className="flex flex-col gap-2.5">
      {(frameworks?.ocean_impact_areas ?? []).map((area) => {
        const items = kpis.filter((k) => k.area_code === area.code && k.evidence_level > 0);
        const best = Math.max(0, ...items.map((k) => k.evidence_level));
        return (
          <div
            className={cx("rounded-lg border border-grid px-3 py-2.5", !items.length && "opacity-55")}
            key={area.code}
          >
            <div className="flex items-center justify-between gap-2">
              <h3>
                <span className={areaCode}>{area.code}</span>
                {area.name}
              </h3>
              <span className="text-small text-muted">
                {items.length ? `${items.length} KPI${items.length > 1 ? "s" : ""} · best ${best}/4` : "Not addressed"}
              </span>
            </div>
            {items.map((k) => (
              <div
                className="mt-2.5 grid grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 border-t border-grid pt-2.5"
                key={k.kpi_code}
              >
                <span className="text-small">
                  <strong>{k.kpi_code}</strong> {k.kpi_name}
                </span>
                <EvidenceDots level={k.evidence_level} label={k.evidence_label} />
                <p className="col-span-full text-small text-fg-2">
                  {k.claim}{" "}
                  {k.source_url ? (
                    <a href={k.source_url} target="_blank" rel="noreferrer">
                      Source <LuExternalLink size={13} className="inline" />
                    </a>
                  ) : (
                    <span className="text-muted">No source</span>
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
