import type { Framework, KPI } from "../../api/types";
import type { DraftErrors } from "../../lib/assessment";
export function ImpactFields({
  kpis,
  framework,
  onChange,
}: {
  kpis: Record<string, KPI>;
  framework: Framework;
  errors: DraftErrors;
  onChange: (code: string, kpi: KPI) => void;
}) {
  return (
    <div>
      {framework.ocean_impact_areas.map((a) => (
        <details className="fw" key={a.code}>
          <summary>
            {a.code} · {a.name}
          </summary>
          {a.kpis.map((k) => (
            <label className="impact-row" key={k.code}>
              <span>{k.name}</span>
              <select
                aria-label={k.name}
                className="select"
                value={kpis[k.code]?.level ?? 0}
                onChange={(e) =>
                  onChange(k.code, { code: k.code, name: k.name, level: Number(e.target.value) })
                }
              >
                {framework.evidence_scale.map((v) => (
                  <option key={v.level} value={v.level}>
                    {v.level} · {v.label}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </details>
      ))}
    </div>
  );
}
