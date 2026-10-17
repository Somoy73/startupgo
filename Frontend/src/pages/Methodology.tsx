import { useAppData } from "@/state/AppData";
import { cx, disclosure, disclosureSummary, EmptyState, PageHeader, Section, stack } from "@/components/ui";

const FW_LIST = "mt-2.5 mb-0 text-md text-fg-2";

export function Methodology() {
  const { frameworks: fw, error } = useAppData();
  if (error) return <EmptyState error>{error}</EmptyState>;
  if (!fw) return <EmptyState>Loading…</EmptyState>;

  const w = fw.potential_weights;
  const pct = (n: number) => `${Math.round(n * 100)}%`;

  return (
    <>
      <PageHeader
        title="Methodology"
        description="How Startup Go scores startups. Every component is transparent and tunable."
      />

      <div className={stack}>
        <Section title="Investment Potential">
          <pre className="overflow-x-auto rounded-lg bg-surface-2 px-3.5 py-3 font-mono text-small">
            {`potential = ${w.readiness} × Readiness index
          + ${w.ocean_impact} × Ocean impact
          + ${w.momentum} × Funding momentum
          − ${fw.penalty_per_extra_level} × max(0, readiness spread − ${fw.max_healthy_spread})

Bands: Strong ≥ 70 · Promising ≥ 55 · Watch ≥ 40 · Early < 40`}
          </pre>
          <p className="mt-2.5 text-small text-fg-2">
            The imbalance penalty follows the KTH IRL guidance that gaps of more than 2–3 levels between dimensions
            hinder development and raise the risk of failure. Funding momentum mixes the funding stage (60%) with the
            recency of the last round (40%, decaying to zero over 48 months).
          </p>
        </Section>

        <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2">
          <Section title="Readiness: KTH Innovation Readiness Level" aside={`${pct(w.readiness)} of potential`}>
            <p className="mb-3 text-small text-fg-2">
              Six dimensions scored 1–9. The index is a weighted mean rescaled so that L1 = 0 and L9 = 100.
            </p>
            {fw.readiness_dimensions.map((d) => (
              <details className={disclosure} key={d.code}>
                <summary className={disclosureSummary}>
                  <span>
                    {d.code} · {d.name}
                  </span>
                  <span className="text-small text-muted">weight {pct(d.weight)}</span>
                </summary>
                <p className="mt-2 text-small text-fg-2">{d.description}</p>
                <ol className={cx(FW_LIST, "list-decimal pl-5.5")}>
                  {d.levels.map((l) => (
                    <li key={l.level} className="py-0.5">
                      {l.summary}
                    </li>
                  ))}
                </ol>
              </details>
            ))}
          </Section>

          <Section title="Ocean impact: Ocean Impact Navigator" aside={`${pct(w.ocean_impact)} of potential`}>
            <p className="mb-2 text-small text-fg-2">
              30 KPIs in 6 impact areas (1000 Ocean Startups / SYSTEMIQ, WEF 2023). Each KPI gets an evidence level:
            </p>
            <p className="mb-3 text-small">{fw.evidence_scale.map((e) => `${e.level} ${e.label}`).join(" · ")}</p>
            <p className="mb-3 text-small text-fg-2">
              Score = 50% strongest evidence + 30% average evidence + 20% breadth (areas covered, capped at 3).
            </p>
            {fw.ocean_impact_areas.map((a) => (
              <details className={disclosure} key={a.code}>
                <summary className={disclosureSummary}>
                  <span>
                    {a.code} · {a.name}
                  </span>
                  <span className="text-small text-muted">{a.kpis.length} KPIs</span>
                </summary>
                <p className="mt-2 text-small text-fg-2">{a.orientation}</p>
                <ol className={cx(FW_LIST, "list-none pl-0")}>
                  {a.kpis.map((k) => (
                    <li key={k.code} className="py-0.5">
                      <strong>{k.code}</strong> {k.name}
                      {k.qualitative_only ? <span className="text-muted"> (qualitative only)</span> : null}
                    </li>
                  ))}
                </ol>
              </details>
            ))}
          </Section>
        </div>
      </div>
    </>
  );
}
