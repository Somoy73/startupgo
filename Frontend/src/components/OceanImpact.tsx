import type { KPI } from "../api/types";
export function OceanImpact({ kpis }: { kpis: KPI[] }) {
  return (
    <div className="stack">
      {kpis.length ? (
        kpis.map((k) => (
          <div className="impact-row" key={k.code}>
            <span>
              <strong>{k.code}</strong> · {k.name}
            </span>
            <span className="chip">
              {["None", "Intent", "Modelled", "Measured", "Verified"][k.level]}
            </span>
          </div>
        ))
      ) : (
        <p className="muted">No impact evidence recorded.</p>
      )}
    </div>
  );
}
