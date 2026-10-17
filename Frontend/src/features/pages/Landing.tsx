import { ArrowRight, CalendarDays, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { backend } from "../../api/backend";
import type { StartupSummary } from "../../api/backend-types";
import { CordisWidget } from "../../components/CordisWidget";
import { Meter } from "../../components/Scores";
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
      .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? "") || (b.founded_year ?? 0) - (a.founded_year ?? 0))
      .slice(0, 5),
    trending: [...assessed].sort((a, b) => b.scores.momentum - a.scores.momentum).slice(0, 5),
    topImpact: [...assessed].sort((a, b) => b.scores.ocean_impact - a.scores.ocean_impact).slice(0, 3),
  };
};

const foundOn = (createdAt: string | null | undefined) => (createdAt ? createdAt.slice(0, 10) : "—");

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
              <h2 id="trending-heading">Trending</h2>
              <span className="small muted">By funding momentum</span>
            </div>
            <div className="rank-list">
              {data.trending.map((s, i) => (
                <RankRow key={s.slug} rank={i + 1} startup={s}>
                  <span className="growth-pill">
                    <TrendingUp /> Momentum {score(s.scores.momentum)}
                  </span>
                </RankRow>
              ))}
            </div>
          </section>

          <section className="dash-card" aria-labelledby="impact-heading">
            <div className="dash-card-head">
              <h2 id="impact-heading">Top ocean impact</h2>
              <span className="small muted">Score out of 100</span>
            </div>
            <div className="rank-list">
              {data.topImpact.map((s, i) => (
                <RankRow key={s.slug} rank={i + 1} startup={s}>
                  <Meter value={s.scores.ocean_impact} label="Ocean impact" />
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
