import { api } from "../api/client";
import { useAsync } from "../lib/useAsync";

export function Methodology() {
  const { data: fw, error } = useAsync(() => api.frameworks(), []);
  if (error) return <p className="empty error">{error}</p>;
  if (!fw) return <p className="empty">Loading…</p>;

  const w = fw.potential_weights;
  const pct = (n: number) => `${Math.round(n * 100)}%`;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Methodology</h1>
          <p>How Startup Go scores startups. Every component is transparent and tunable.</p>
        </div>
      </div>

      <div className="stack">
        <section className="card card-pad">
          <div className="card-head"><h2>Investment Potential</h2></div>
          <pre className="formula">
{`potential = ${w.readiness} × Readiness index
          + ${w.ocean_impact} × Ocean impact
          + ${w.momentum} × Funding momentum
          − ${fw.penalty_per_extra_level} × max(0, readiness spread − ${fw.max_healthy_spread})

Bands: Strong ≥ 70 · Promising ≥ 55 · Watch ≥ 40 · Early < 40`}
          </pre>
          <p className="small secondary" style={{ marginTop: 10 }}>
            The imbalance penalty follows the KTH IRL guidance that gaps of more than 2–3 levels between dimensions
            hinder development and raise the risk of failure. Funding momentum mixes the funding stage (60%) with the
            recency of the last round (40%, decaying to zero over 48 months).
          </p>
        </section>

        <div className="grid grid-2" style={{ alignItems: "start" }}>
          <section className="card card-pad">
            <div className="card-head">
              <h2>Readiness: KTH Innovation Readiness Level</h2>
              <span className="small muted">{pct(w.readiness)} of potential</span>
            </div>
            <p className="small secondary" style={{ marginBottom: 12 }}>
              Six dimensions scored 1–9. The index is a weighted mean rescaled so that L1 = 0 and L9 = 100.
            </p>
            {fw.readiness_dimensions.map((d) => (
              <details className="fw" key={d.code}>
                <summary>
                  <span>{d.code} · {d.name}</span>
                  <span className="small muted">weight {pct(d.weight)}</span>
                </summary>
                <p className="small secondary" style={{ marginTop: 8 }}>{d.description}</p>
                <ol>
                  {d.levels.map((l) => (
                    <li key={l.level}>{l.summary}</li>
                  ))}
                </ol>
              </details>
            ))}
          </section>

          <section className="card card-pad">
            <div className="card-head">
              <h2>Ocean impact: Ocean Impact Navigator</h2>
              <span className="small muted">{pct(w.ocean_impact)} of potential</span>
            </div>
            <p className="small secondary" style={{ marginBottom: 8 }}>
              30 KPIs in 6 impact areas (1000 Ocean Startups / SYSTEMIQ, WEF 2023). Each KPI gets an evidence level:
            </p>
            <p className="small" style={{ marginBottom: 12 }}>
              {fw.evidence_scale.map((e) => `${e.level} ${e.label}`).join(" · ")}
            </p>
            <p className="small secondary" style={{ marginBottom: 12 }}>
              Score = 50% strongest evidence + 30% average evidence + 20% breadth (areas covered, capped at 3).
            </p>
            {fw.ocean_impact_areas.map((a) => (
              <details className="fw" key={a.code}>
                <summary>
                  <span>{a.code} · {a.name}</span>
                  <span className="small muted">{a.kpis.length} KPIs</span>
                </summary>
                <p className="small secondary" style={{ marginTop: 8 }}>{a.orientation}</p>
                <ol style={{ listStyle: "none", paddingLeft: 0 }}>
                  {a.kpis.map((k) => (
                    <li key={k.code}>
                      <strong>{k.code}</strong> {k.name}
                      {k.qualitative_only ? <span className="muted"> (qualitative only)</span> : null}
                    </li>
                  ))}
                </ol>
              </details>
            ))}
          </section>
        </div>
      </div>
    </>
  );
}
