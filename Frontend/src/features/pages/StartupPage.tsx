import { useCallback, useState } from "react";
import { Link, useParams } from "../../lib/navigation";
import { ApiError, backend } from "../../api/backend";
import { FundingTable } from "../../components/FundingTable";
import { FundingTimeline, FundingTotal } from "../../components/FundingTimeline";
import { IconAlert, IconBack, IconExternal } from "../../components/Icons";
import { OceanImpactSection } from "../../components/OceanImpactSection";
import { ReadinessSection } from "../../components/ReadinessSection";
import { ResearchPanel } from "../../components/ResearchPanel";
import { PeerScatter } from "../../components/PeerScatter";
import { PotentialBreakdown } from "../../components/PotentialBreakdown";
import { PotentialMark } from "../../components/PotentialMark";
import { BandBadge } from "../../components/Scores";
import { partialDate, stageLabel } from "../../lib/format";
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
  // For the charts. Each loads on its own; one failing only hides its chart.
  const { data: frameworks } = useAsync(() => backend.frameworks(), []);
  const { data: startups } = useAsync(() => backend.startups(), [reloads]);
  const { data: peers } = useAsync(() => backend.peers(slug), [slug]);
  const { data: events } = useAsync(() => backend.rounds(slug), [slug]);

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
                <ul className="space-y-1.5 text-sm">
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

        {/* Left Column Stack: the scores, once the startup is assessed */}
        <div className="stack">
          {assessed && (
            <>
              <ReadinessSection levels={s.levels} readiness={readiness} scores={scores} />
              {frameworks && (
                <PotentialBreakdown scores={scores} weights={frameworks.potential_weights} />
              )}
              {startups && <PeerScatter slug={s.slug} startups={startups} peers={peers ?? []} />}
            </>
          )}
        </div>

        {/* Right Column Stack */}
        <div className="stack">
          <OceanImpactSection kpis={s.ocean_kpis} areas={frameworks?.ocean_impact_areas ?? null} />

          <section className="card card-pad">
            <div className="card-head">
              <h2>Funding</h2>
              <FundingTotal events={events} disclosedUsd={s.total_disclosed_usd} />
            </div>
            {events === null ? (
              <p className="small muted">Loading funding events…</p>
            ) : events.length === 0 ? (
              <p className="small muted">No funding events recorded.</p>
            ) : (
              <>
                <FundingTimeline events={events} />
                <FundingTable events={events} />
              </>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
