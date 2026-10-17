import { useCallback, useState } from "react";
import { Link, useParams } from "../../lib/navigation";
import { ApiError, backend } from "../../api/backend";
import { IconAlert, IconBack, IconExternal } from "../../components/Icons";
import { OceanImpact } from "../../components/OceanImpact";
import { ReadinessSection } from "../../components/ReadinessSection";
import { ResearchPanel } from "../../components/ResearchPanel";
import { PotentialMark } from "../../components/PotentialMark";
import { BandBadge } from "../../components/Scores";
import { compactMoney, partialDate, stageLabel } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";

/** Loads the profile from the backend; a 404 means the slug isn't in the database. */
const loadStartup = (slug: string) =>
  backend.startup(slug).catch((e: unknown) => {
    if (e instanceof ApiError && e.status === 404)
      throw new Error(
        `No startup “${slug}” in the database. Pages other than this one still show sample data.`,
      );
    throw e;
  });

export function StartupPage() {
  const { slug = "" } = useParams();
  const [reloads, setReloads] = useState(0);
  const reload = useCallback(() => setReloads((n) => n + 1), []);
  const { data: s, error, loading } = useAsync(() => loadStartup(slug), [slug, reloads]);

  if (error) return <p className="empty error">{error}</p>;
  if (loading || !s) return <p className="empty">Loading…</p>;

  const { scores, readiness, assessed } = s;

  return (
    <>
      <Link to="/" className="back">
        <IconBack /> Back
      </Link>
      <div className="page-head">
        <div>
          <div className="row-gap" style={{ marginBottom: 6 }}>
            <h1>{s.name}</h1>
            {assessed && <BandBadge band={scores.band} />}
          </div>
          <p>{s.tagline}</p>
          <p className="small muted" style={{ marginTop: 6 }}>
            {s.sector} ·{" "}
            {[s.city, s.country].filter((x, i, a) => x && a.indexOf(x) === i).join(", ")}
            {s.founded_year && ` · Founded ${s.founded_year}`} · {stageLabel(s.stage)}
            {s.website && (
              <>
                {" · "}
                <a href={s.website} target="_blank" rel="noreferrer">
                  Website <IconExternal />
                </a>
              </>
            )}
          </p>
        </div>
        {assessed && <PotentialMark scores={scores} />}
      </div>

      {!assessed && <ResearchPanel slug={s.slug} onDone={reload} />}

      {assessed && readiness.confidence === "low" && (
        <div className="notice">
          <IconAlert />
          <span>
            Readiness and impact-evidence levels are a <strong>{readiness.assessor}</strong> (
            {partialDate(readiness.assessed_on)}, confidence: low) built from public sources.
            Validate with the founders before relying on them.
          </span>
        </div>
      )}

      
        {/* Changed from flex flex-wrap to 2-column grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4" style={{ alignItems: "start" }}>
          <section className="card card-pad md:col-span-2">
            <div className="card-head">
              <h2>About</h2>
            </div>
            <p className="secondary">{s.description}</p>
          </section>

          {/* Left Column Stack */}
          <div className="stack">
            {assessed && (
              <ReadinessSection levels={s.levels} readiness={readiness} scores={scores} />
            )}
          </div>

          {/* Right Column Stack */}
          <div className="stack">
            <section className="card card-pad">
              <div className="card-head">
                <h2>Ocean impact</h2>
                <span className="small muted">Ocean Impact Navigator · evidence 0–4</span>
              </div>
              <OceanImpact kpis={s.ocean_kpis} />
            </section>

            <section className="card card-pad">
              <div className="card-head">
                <h2>Sources</h2>
              </div>
              {s.sources.length === 0 && <p className="small muted">No sources recorded.</p>}
              <ul style={{ margin: 0, paddingLeft: 18, listStyle: "disc" }}>
                {s.sources.map((src) => (
                  <li key={src.url}>
                    <a href={src.url} target="_blank" rel="noreferrer">
                      {src.title}
                    </a>
                  </li>
                ))}
              </ul>
            </section>

            <section className="card card-pad">
              <div className="card-head">
                <h2>Funding rounds</h2>
                <span className="small muted">
                  Total disclosed ≈ {compactMoney(s.total_disclosed_usd)}
                </span>
              </div>
              {s.funding_rounds.length === 0 && (
                <p className="small muted">No funding rounds recorded.</p>
              )}
              {s.funding_rounds.length > 0 && (
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr>
                        <th>Round</th>
                        <th>Date</th>
                        <th className="num">Amount</th>
                        <th>Lead</th>
                      </tr>
                    </thead>
                    <tbody>
                      {s.funding_rounds.map((r, i) => (
                        <tr key={i}>
                          <td>
                            {stageLabel(r.round_type)}
                            {r.source_url && (
                              <>
                                {" "}
                                <a
                                  href={r.source_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  aria-label="Source"
                                >
                                  <IconExternal />
                                </a>
                              </>
                            )}
                          </td>
                          <td className="tabular">{partialDate(r.announced_on)}</td>
                          <td className="num">
                            {r.amount != null && r.currency
                              ? compactMoney(r.amount, r.currency)
                              : "Undisclosed"}
                          </td>
                          <td className="small secondary">
                            {r.lead_investors}
                            {r.notes && <div className="muted">{r.notes}</div>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        </div>
      
    </>
  );
}
