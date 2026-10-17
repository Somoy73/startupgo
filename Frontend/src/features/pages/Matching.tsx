import { useMemo, useState } from "react";
import { MatchRadar } from "../../components/matching/MatchRadar";
import { TopMatchList } from "../../components/matching/TopMatchList";
import { topInvestorMatches } from "../../lib/investor";
import { useAppData } from "../../state/AppData";

export function Matching() {
  const { startups, loading, error } = useAppData();
  const [hovered, setHovered] = useState<string | null>(null);
  const matches = useMemo(() => topInvestorMatches(startups, 5), [startups]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Matching</h1>
          <p>The best matches based our agent judge scoring. A'Pelago is in the center and the graph represents the closest startup matches.</p>
        </div>
      </div>

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
              <MatchRadar matches={matches} hovered={hovered} onHover={setHovered} />
            </div>
            <div className="mg-list">
              <h2 className="mg-eyebrow">Top matches</h2>
              <TopMatchList matches={matches} hovered={hovered} onHover={setHovered} />
            </div>
          </div>
        )}
      </section>
    </>
  );
}
