import { useMemo, useState } from "react";
import { MatchRadar } from "../../components/matching/MatchRadar";
import { TopMatchList } from "../../components/matching/TopMatchList";
import { backend } from "../../api/backend";
import { rankByReadiness, similarStartups } from "../../lib/readiness-ranking";
import { useAsync } from "../../lib/useAsync";

export function Matching() {
  const { data: startups, loading, error } = useAsync(() => backend.startups(), []);
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const toggle = (slug: string) => setSelected((cur) => (cur === slug ? null : slug));
  const ranked = useMemo(() => rankByReadiness(startups ?? [], Infinity), [startups]);
  const matches = ranked.slice(0, 10);
  const picked = ranked.find((m) => m.startup.slug === selected) ?? null;
  const similar = picked ? similarStartups(picked, ranked) : [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Matching</h1>
          <p>
            Startups ranked by their readiness index from the StartupGo database, highest first.
            Only startups with a completed assessment are ranked.
          </p>
        </div>
      </div>

      <div className={`mg-layout${picked ? " is-open" : ""}`}>
        <section className="card mg-card">
          <header className="mg-head">
            <span className="mg-dot" aria-hidden />
            Readiness ranking
          </header>
          {error && <p className="small error card-pad">{error}</p>}
          {!loading && matches.length === 0 && <p className="empty">No assessed startups yet.</p>}
          {matches.length > 0 && (
            <div className="mg-body">
              <div className="mg-graph">
                <MatchRadar matches={matches} hovered={hovered} selected={selected} onHover={setHovered} onSelect={toggle} />
              </div>
              <div className="mg-list">
                <h2 className="mg-eyebrow">Top matches</h2>
                <TopMatchList matches={matches} hovered={hovered} selected={selected} onHover={setHovered} onSelect={toggle} />
              </div>
            </div>
          )}
        </section>
        {picked && (
          <aside className="mg-detail" aria-live="polite" key={picked.startup.slug}>
            <div className="mg-detail-inner">
              <button type="button" className="mg-close" onClick={() => setSelected(null)} aria-label="Close details">×</button>
              <p className="mg-eyebrow">{picked.startup.sector} · {picked.startup.country}</p>
              <h3>{picked.startup.name}</h3>
              <p className="mg-detail-score">{picked.total}<small> / 100 readiness</small></p>
              <p>{picked.startup.description}</p>
              <dl>
                <div><dt>Readiness</dt><dd>{picked.readiness}</dd></div>
                <div><dt>Ocean impact</dt><dd>{picked.impact}</dd></div>
                <div><dt>Investment potential</dt><dd>{picked.potential}</dd></div>
              </dl>
            </div>
            {similar.length > 0 && (
              <section className="mg-similar" aria-label="Similar startups">
                <h4 className="mg-eyebrow">Startups you might also be interested in</h4>
                <div className="mg-similar-grid">
                  {similar.map((r) => (
                    <button type="button" key={r.startup.slug} className="mg-similar-card" onClick={() => setSelected(r.startup.slug)}>
                      <span className="tm-badge" aria-hidden>{r.startup.name[0]}</span>
                      <strong>{r.startup.name}</strong>
                      <small>{r.startup.sector}</small>
                      <span className="mg-similar-score">{r.total}<small> readiness</small></span>
                    </button>
                  ))}
                </div>
              </section>
            )}
          </aside>
        )}
      </div>
    </>
  );
}
