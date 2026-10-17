import { ArrowRight, CalendarDays, Trophy, Waves } from "lucide-react";
import type { ReactNode } from "react";
import { backend } from "../../api/backend";
import type { StartupSummary } from "../../api/backend-types";
import { CordisWidget } from "../../components/CordisWidget";
import { score } from "../../lib/format";
import { Link } from "../../lib/navigation";
import { navItems } from "../../lib/nav-items";
import { useAsync } from "../../lib/useAsync";

/** The dashboards, from the startups in the database (GET /api/startups). */
const dashboards = (startups: StartupSummary[]) => {
  const assessed = startups.filter((s) => s.assessed);
  return {
    // Most recently found first; startups found in the same batch, youngest company first.
    newest: [...startups]
      .sort(
        (a, b) =>
          (b.created_at ?? "").localeCompare(a.created_at ?? "") ||
          (b.founded_year ?? 0) - (a.founded_year ?? 0),
      )
      .slice(0, 5),
    // The VC Investment Score (the agent's rubric, 0-100), highest first.
    topVc: startups
      .filter((s) => s.investment?.investment_percent != null)
      .sort((a, b) => vcScore(b) - vcScore(a) || a.name.localeCompare(b.name))
      .slice(0, 5),
    // Ocean Impact Readiness (1-5), highest first; ties by the ocean impact score.
    topImpact: startups
      .filter((s) => s.investment?.ocean_impact_readiness != null)
      .sort((a, b) => oir(b) - oir(a) || b.scores.ocean_impact - a.scores.ocean_impact)
      .slice(0, 3),
  };
};

const vcScore = (s: StartupSummary) => s.investment?.investment_percent ?? 0;
const oir = (s: StartupSummary) => s.investment?.ocean_impact_readiness ?? 0;

const foundOn = (createdAt: string | null | undefined) =>
  createdAt ? createdAt.slice(0, 10) : "—";

export function Landing() {
  const { data, loading, error } = useAsync(() => backend.startups().then(dashboards), []);

  return (
    <div className="landing">
      <div className="page-head">
        <div>
          <h1>Startups in Finnish Blue Economy</h1>
          <p>Discover the newest startups found and assessed by our agentic approach.</p>
          <nav className="hero-nav" aria-label="Main navigation">
            {navItems.map((item) => (
              <Link key={item.to} to={item.to}>
                {item.name}
              </Link>
            ))}
          </nav>
        </div>
      </div>

      {loading && <p className="empty">Loading dashboards…</p>}
      {error && <p className="empty error">Couldn't load dashboards: {error}</p>}

      {data && (
        <div className="dash-grid">
          <section className="dash-card" aria-labelledby="newest-heading">
            <div className="dash-card-head">
              <h2 id="newest-heading">Newest startups</h2>
              <Link to="/search" className="dash-more">
                View all <ArrowRight />
              </Link>
            </div>
            <div className="rank-list">
              {data.newest.map((s, i) => (
                <RankRow key={s.slug} rank={i + 1} startup={s}>
                  <span className="meta">
                    <CalendarDays /> Found {foundOn(s.created_at)}
                  </span>
                </RankRow>
              ))}
            </div>
          </section>

          <section className="dash-card" aria-labelledby="cordis-heading">
            <div className="dash-card-head">
              <h2 id="cordis-heading">EU ocean projects</h2>
              <Link to="/eu-projects" className="dash-more">
                More <ArrowRight />
              </Link>
            </div>
            <CordisWidget output="map" />
          </section>

          <section className="dash-card" aria-labelledby="trending-heading">
            <div className="dash-card-head">
              <h2 id="trending-heading">Top VC startups</h2>
              <span className="small muted">VC investment score out of 100</span>
            </div>
            <div className="rank-list">
              {data.topVc.map((s, i) => (
                <RankRow key={s.slug} rank={i + 1} startup={s}>
                  <span
                    className="growth-pill"
                    title="VC investment score: the agent's rubric on 10 criteria, 0-100"
                  >
                    <Trophy /> {score(vcScore(s))}
                  </span>
                </RankRow>
              ))}
            </div>
          </section>

          <section className="dash-card" aria-labelledby="impact-heading">
            <div className="dash-card-head">
              <h2 id="impact-heading">Top ocean impact</h2>
              <span className="small muted">Ocean Impact Readiness (OIR) out of 5</span>
            </div>
            <div className="rank-list">
              {data.topImpact.map((s, i) => (
                <RankRow key={s.slug} rank={i + 1} startup={s}>
                  <span className="growth-pill" title="Ocean Impact Readiness, 1-5">
                    <Waves /> OIR {oir(s)}/5
                  </span>
                </RankRow>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function RankRow({
  rank,
  startup,
  children,
}: {
  rank: number;
  startup: StartupSummary;
  children?: ReactNode;
}) {
  return (
    <div className="rank-row">
      <span className="rank-badge">{rank}</span>
      <Link to={`/startups/${startup.slug}`} className="grow rank-link">
        <span className="name">{startup.name}</span>
        <span className="meta">
          {startup.sector} · {startup.country} ·{" "}
          {startup.assessed ? `Potential ${score(startup.scores.potential)}` : "Not assessed yet"}
        </span>
      </Link>
      {children}
    </div>
  );
}
