import { Link, useParams } from "../../lib/navigation";
import { ApiError, backend } from "../../api/backend";
import { FundingTimeline } from "../../components/FundingTimeline";
import { IconAlert, IconBack, IconExternal } from "../../components/Icons";
import { OceanAreaChart } from "../../components/OceanAreaChart";
import { OceanImpact } from "../../components/OceanImpact";
import { ReadinessSection } from "../../components/ReadinessSection";
import { PeerScatter } from "../../components/PeerScatter";
import { PotentialBreakdown } from "../../components/PotentialBreakdown";
import { PotentialMark } from "../../components/PotentialMark";
import { BandBadge } from "../../components/Scores";
import { compactMoney, partialDate, stageLabel, toEur } from "../../lib/format";
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
  const { data: s, error, loading } = useAsync(() => loadStartup(slug), [slug]);
  // For the charts. Each loads on its own; one failing only hides its chart.
  const { data: frameworks } = useAsync(() => backend.frameworks(), []);
  const { data: startups } = useAsync(() => backend.startups(), []);
  const { data: peers } = useAsync(() => backend.peers(slug), [slug]);
  const { data: events } = useAsync(() => backend.rounds(slug), [slug]);

  if (error) return <p className="empty error">{error}</p>;
  if (loading || !s) return <p className="empty">Loading…</p>;

  const { scores, readiness } = s;

  return (
    <>
      <Link to="/" className="back">
        <IconBack /> Back
      </Link>
      <div className="page-head">
        <div>
          <div className="row-gap" style={{ marginBottom: 6 }}>
            <h1>{s.name}</h1>
            <BandBadge band={scores.band} />
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
        <PotentialMark scores={scores} />
      </div>

      {readiness.confidence === "low" && (
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
          <div className="grid gap-4 md:grid-cols-[3fr_1fr] md:gap-6">
            <div>
              <div className="card-head">
                <h2>About</h2>
              </div>
              <p className="secondary">{s.description}</p>
            </div>
            {s.sources.length > 0 && (
              <div className="border-t border-border pt-3 md:border-t-0 md:border-l md:pt-0 md:pl-6">
                <h3 className="mb-1.5 text-xs font-bold text-muted-foreground">Sources</h3>
                <ul className="grid gap-1.5 text-sm">
                  {s.sources.map((src) => (
                    <li key={src.url}>
                      <a href={src.url} target="_blank" rel="noreferrer">
                        {src.title} <IconExternal className="inline size-3" />
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>

        {/* Left Column Stack */}
        <div className="stack">
          <ReadinessSection levels={s.levels} readiness={readiness} scores={scores} />
          {frameworks && (
            <PotentialBreakdown scores={scores} weights={frameworks.potential_weights} />
          )}
          {startups && <PeerScatter slug={s.slug} startups={startups} peers={peers ?? []} />}
        </div>

        {/* Right Column Stack */}
        <div className="stack">
          <section className="card card-pad">
            <div className="card-head">
              <h2>Ocean impact</h2>
              <span className="small muted">Ocean Impact Navigator · evidence 0–4</span>
            </div>
            {frameworks && (
              <OceanAreaChart areas={frameworks.ocean_impact_areas} kpis={s.ocean_kpis} />
            )}
            <OceanImpact kpis={s.ocean_kpis} />
          </section>

          <section className="card card-pad">
            <div className="card-head">
              <h2>Funding rounds</h2>
              <span className="small muted">
                Total disclosed ≈ {compactMoney(toEur(s.total_disclosed_usd, "USD"))}
              </span>
            </div>
            {events && <FundingTimeline events={events} />}
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
                          {r.source_url ? (
                            <a
                              href={r.source_url}
                              target="_blank"
                              rel="noreferrer"
                              title="Open source"
                              className="inline-flex items-center gap-1 whitespace-nowrap"
                            >
                              {stageLabel(r.round_type)}
                              <IconExternal aria-hidden className="size-3" />
                            </a>
                          ) : (
                            stageLabel(r.round_type)
                          )}
                        </td>
                        <td className="tabular">{partialDate(r.announced_on)}</td>
                        <td className="num">
                          {compactMoney(toEur(r.amount, r.currency))}
                          {r.amount != null && r.currency && r.currency.toUpperCase() !== "EUR" && (
                            <div className="small muted">{compactMoney(r.amount, r.currency)}</div>
                          )}
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
