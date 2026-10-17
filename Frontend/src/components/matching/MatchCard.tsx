import { Link } from "../../lib/navigation";
import { Button } from "../ui/button";
import { Meter } from "../Scores";
import { matchBand, type Match } from "../../lib/matching";
export function MatchCard({
  rank,
  match: m,
  onShortlist,
}: {
  rank: number;
  match: Match;
  onShortlist: (slug: string) => void;
}) {
  return (
    <article className="match-card">
      <div className="row">
        <div>
          <span className="small muted">{String(rank).padStart(2, "0")}</span>
          <Link to={`/startups/${m.startup.slug}`}>
            <h2>{m.startup.name}</h2>
          </Link>
          <p className="secondary small">{m.startup.tagline}</p>
        </div>
        <span className="chip">{matchBand(m)}</span>
      </div>
      <div className="row">
        <p className="small secondary">{m.reasons.join(" · ")}</p>
        <Button variant="outline" onClick={() => onShortlist(m.startup.slug)}>
          Shortlist
        </Button>
      </div>
      <Meter value={m.fit} label="Thesis fit" />
    </article>
  );
}
