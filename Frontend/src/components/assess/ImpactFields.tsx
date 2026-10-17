import type { Frameworks } from "@/api/types";
import { EMPTY_KPI, type DraftErrors, type KpiDraft } from "@/lib/assessment";
import { areaCode, disclosure, disclosureSummary, formGrid, Segmented, TextField } from "@/components/ui";

const EVIDENCE = [0, 1, 2, 3, 4];

interface Props {
  kpis: Record<string, KpiDraft>;
  framework: Frameworks;
  errors: DraftErrors;
  onChange: (code: string, kpi: KpiDraft) => void;
}

/** Ocean Impact Navigator KPIs grouped by impact area, each with an evidence level 0-4. */
export function ImpactFields({ kpis, framework, errors, onChange }: Props) {
  const evidenceLabel = (n: number) => framework.evidence_scale.find((e) => e.level === n)?.label ?? String(n);

  return (
    <div className="flex flex-col gap-2">
      <p className="text-small text-fg-2">
        Evidence: {framework.evidence_scale.map((e) => `${e.level} ${e.label}`).join(" · ")}. Only KPIs above 0 are
        saved.
      </p>
      {framework.ocean_impact_areas.map((area) => {
        const active = area.kpis.filter((k) => (kpis[k.code]?.level ?? 0) > 0).length;
        return (
          <details className={disclosure} key={area.code} open={active > 0}>
            <summary className={disclosureSummary}>
              <span>
                <span className={areaCode}>{area.code}</span>
                {area.name}
              </span>
              <span className="text-small text-muted">
                {active ? `${active} selected` : `${area.kpis.length} KPIs`}
              </span>
            </summary>
            {area.kpis.map((k) => {
              const kpi = kpis[k.code] ?? EMPTY_KPI;
              const set = (patch: Partial<KpiDraft>) => onChange(k.code, { ...kpi, ...patch });
              return (
                <div className="flex flex-col gap-2.5 border-t border-grid py-2.5 first-of-type:mt-2.5" key={k.code}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <span className="text-small">
                      <strong>{k.code}</strong> {k.name}
                    </span>
                    <Segmented
                      label={`${k.code} evidence level`}
                      values={EVIDENCE}
                      value={kpi.level}
                      onChange={(level) => set({ level })}
                      describe={evidenceLabel}
                    />
                  </div>
                  {kpi.level > 0 && (
                    <div className={formGrid}>
                      <TextField
                        label="Claim"
                        value={kpi.claim}
                        onChange={(claim) => set({ claim })}
                        error={errors[`kpi.${k.code}`]}
                        placeholder="What impact, how much, how measured"
                        required
                      />
                      <TextField
                        label="Source link"
                        value={kpi.sourceUrl}
                        onChange={(sourceUrl) => set({ sourceUrl })}
                        placeholder="https://"
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </details>
        );
      })}
    </div>
  );
}
