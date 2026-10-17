import { Link } from "../../lib/navigation";
import { useAppData } from "../../state/AppData";

const STEPS = [
  {
    name: "Collect evidence",
    body: "Public sources, founder interviews and documents are gathered into one profile: technology, business model, customers, funding history, intellectual property and team.",
  },
  {
    name: "Score readiness",
    body: "Each readiness dimension is rated 1–9 on the KTH Innovation Readiness Level scale. Every level has a written summary, so the rating is always traceable to a definition.",
  },
  {
    name: "Score ocean impact",
    body: "Impact KPIs are marked with an evidence level. The score shows what a company has actually proven and what it only claims — breadth of coverage counts too.",
  },
  {
    name: "Sign off",
    body: "An assessor records the levels, a confidence level and a short rationale. Assessments are stored with their date, so you can follow how a startup develops.",
  },
  {
    name: "Compare on one number",
    body: "Readiness, ocean impact and funding momentum are combined into an investment-potential score out of 100, with a band and a breakdown of what holds it back.",
  },
];

/** /assess — information page about the assessment method. */
export function Assess() {
  const { frameworks: fw, error } = useAppData();
  if (error) return <p className="empty error">{error}</p>;
  if (!fw) return <p className="empty">Loading…</p>;

  const w = fw.potential_weights;
  const pct = (n: number) => `${Math.round(n * 100)}%`;
  const kpiCount = fw.ocean_impact_areas.reduce((sum, a) => sum + a.kpis.length, 0);

  return (
    <>
      <div className="page-head ">
        <div>
          <h1>Information about our assess methods</h1>
          <p>
            How our judge agent assess startups. Choose a startup from landing page or
            search page to see its assessment
          </p>
          <div style={{ marginTop: 24 }}>
            <Link to="/search" className="btn btn-primary !px-10 !py-4 !text-lg border-white border-1">
              Go assessing
            </Link>
          </div>
        </div>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        <div className="card stat">
          <span className="label">Readiness dimensions</span>
          <span className="value">{fw.readiness_dimensions.length}</span>
          <span className="sub">each scored 1–9</span>
        </div>
        <div className="card stat">
          <span className="label">Ocean impact KPIs</span>
          <span className="value">{kpiCount}</span>
          <span className="sub">across {fw.ocean_impact_areas.length} areas</span>
        </div>
        <div className="card stat">
          <span className="label">Evidence levels</span>
          <span className="value">{fw.evidence_scale.length}</span>
          <span className="sub">recorded per KPI</span>
        </div>
        <div className="card stat">
          <span className="label">Score inputs</span>
          <span className="value">3</span>
          <span className="sub">readiness · impact · momentum</span>
        </div>
      </div>

      <div className="stack">
        <section className="card card-pad">
          <div className="card-head">
            <h2>The method, step by step</h2>
          </div>
          <div className="rank-list">
            {STEPS.map((step, i) => (
              <div className="rank-row" key={step.name}>
                <span className="rank-badge">{i + 1}</span>
                <div className="grow">
                  <span className="name">{step.name}</span>
                  <p className="small secondary" style={{ marginTop: 4 }}>
                    {step.body}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="grid grid-2" style={{ alignItems: "start" }}>
          <section className="card card-pad">
            <div className="card-head">
              <h2>Readiness</h2>
              <span className="small muted">{pct(w.readiness)} of the score</span>
            </div>
            <p className="small secondary" style={{ marginBottom: 8 }}>
              KTH Innovation Readiness Level. Six dimensions, weighted below, rescaled so that L1 =
              0 and L9 = 100.
            </p>
            <div className="rank-list">
              {fw.readiness_dimensions.map((d) => (
                <div className="rank-row" key={d.code}>
                  <div className="grow">
                    <span className="name">
                      {d.code} · {d.name}
                    </span>
                    <span className="meta">{d.description}</span>
                  </div>
                  <span className="chip">{pct(d.weight)}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="card card-pad">
            <div className="card-head">
              <h2>Ocean impact</h2>
              <span className="small muted">{pct(w.ocean_impact)} of the score</span>
            </div>
            <p className="small secondary" style={{ marginBottom: 8 }}>
              Ocean Impact Navigator. {kpiCount} KPIs in {fw.ocean_impact_areas.length} areas, each
              marked with an evidence level.
            </p>
            <div className="rank-list">
              {fw.ocean_impact_areas.map((a) => (
                <div className="rank-row" key={a.code}>
                  <div className="grow">
                    <span className="name">
                      {a.code} · {a.name}
                    </span>
                    <span className="meta">{a.orientation}</span>
                  </div>
                  <span className="chip">{a.kpis.length} KPIs</span>
                </div>
              ))}
            </div>
            <p className="small muted" style={{ marginTop: 12 }}>
              Evidence: {fw.evidence_scale.map((e) => `${e.level} ${e.label}`).join(" · ")}
            </p>
          </section>
        </div>

        <section className="card card-pad">
          <div className="card-head">
            <h2>Funding momentum</h2>
            <span className="small muted">{pct(w.momentum)} of the score</span>
            Where a company is in its funding history and how recently it last raised. A round
            closed this quarter counts for more than one from four years ago, so momentum is a
            signal of traction rather than of size.
          </div>
        </section>

        <section className="card card-pad">
          <div className="card-head">
            <h2>What the score tells you</h2>
          </div>
          <p className="small secondary" style={{ marginBottom: 10 }}>
            Investment potential is a weighted blend of readiness ({pct(w.readiness)}), ocean impact
            ({pct(w.ocean_impact)}) and funding momentum ({pct(w.momentum)}).
          </p>
          <div className="row-gap" style={{ flexWrap: "wrap" }}>
            <span className="chip">Strong ≥ 70</span>
            <span className="chip">Promising ≥ 55</span>
            <span className="chip">Watch ≥ 40</span>
            <span className="chip">Early &lt; 40</span>
          </div>
          <p className="small secondary" style={{ marginTop: 14 }}>
            The exact formula and weights are all shown on this page. You can also see the method
            applied side by side in <Link to="/matching">Matching</Link>.
          </p>
        </section>
      </div>
    </>
  );
}
