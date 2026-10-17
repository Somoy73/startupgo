import { ArrowRight, CalendarDays, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { api } from "../../api/client";
import type { StartupDetail } from "../../api/types";
import { Meter } from "../../components/Scores";
import { partialDate, score } from "../../lib/format";
import { Link } from "../../lib/navigation";
import { navItems } from "../../lib/nav-items";
import { useAsync } from "../../lib/useAsync";

export function Landing() {
  const { data, loading, error } = useAsync(() => api.landingDashboard(), []);

  return (
    <div className="landing">
      <div className="page-head">
        <div>
          <h1>Startups in Finnish Blue Economy</h1>
          <p>
            Discover the newest startups found and assessed by our agentic approach.
          </p>
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
          <section className="dash-card span-full" aria-labelledby="newest-heading">
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
                    <CalendarDays /> Found {partialDate(s.created_at)}
                  </span>
                </RankRow>
              ))}
            </div>
          </section>

          <section className="dash-card" aria-labelledby="trending-heading">
            <div className="dash-card-head">
              <h2 id="trending-heading">Trending</h2>
              <span className="small muted">By growth speed</span>
            </div>
            <div className="rank-list">
              {data.trending.map((s, i) => (
                <RankRow key={s.slug} rank={i + 1} startup={s}>
                  <span className="growth-pill">
                    <TrendingUp /> +{s.growth_speed ?? 0}%/mo
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
  startup: StartupDetail;
  children?: ReactNode;
}) {
  return (
    <div className="rank-row">
      <span className="rank-badge">{rank}</span>
      <Link to={`/startups/${startup.slug}`} className="grow rank-link">
        <span className="name">{startup.name}</span>
        <span className="meta">
          {startup.sector} · {startup.country} · Potential {score(startup.scores.potential)}
        </span>
      </Link>
      {children}
    </div>
  );
}
