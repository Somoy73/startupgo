import { useMemo, useState } from "react";
import { MatchRadar } from "../../components/matching/MatchRadar";
import { TopMatchList } from "../../components/matching/TopMatchList";
import { topInvestorMatches } from "../../lib/investor";
import { useAppData } from "../../state/AppData";

export function Matching() {
  const { startups, loading, error } = useAppData();
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const toggle = (slug: string) => setSelected((cur) => (cur === slug ? null : slug));
  const matches = useMemo(() => topInvestorMatches(startups, 5), [startups]);
  const picked = matches.find((m) => m.startup.slug === selected) ?? null;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Matching</h1>
          <p>The best matches based our agent judge scoring. A'Pelago is in the center and the graph represents the closest startup matches.</p>
        </div>
      </div>

      <div className={`mg-layout${picked ? " is-open" : ""}`}>
        <section className="card mg-card">
          <header className="mg-head">
            <span className="mg-dot" aria-hidden />
            Investor match
          </header>
          {error && <p className="small error card-pad">{error}</p>}
          {!loading && matches.length === 0 && <p className="empty">No startups to match yet.</p>}
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
          <aside className="mg-detail" aria-live="polite">
            <div className="mg-detail-inner" key={picked.startup.slug}>
              <button type="button" className="mg-close" onClick={() => setSelected(null)} aria-label="Close details">×</button>
              <p className="mg-eyebrow">{picked.startup.sector} · {picked.startup.region}</p>
              <h3>{picked.startup.name}</h3>
              <p className="mg-detail-score">{picked.total}<small> / 100 match</small></p>
              <p>{picked.startup.description}</p>
              <dl>
                <div><dt>Thesis fit</dt><dd>{picked.thesis}</dd></div>
                <div><dt>Readiness</dt><dd>{picked.readiness}</dd></div>
                <div><dt>Ocean impact</dt><dd>{picked.impact}</dd></div>
              </dl>
            </div>
          </aside>
        )}
      </div>
    </>
  );
}
