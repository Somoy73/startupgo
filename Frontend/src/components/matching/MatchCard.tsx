import { Link } from "react-router-dom";
import { PIPELINE_LABELS } from "../../lib/format";
import { matchBand, type Match } from "../../lib/matching";
import { IconCheck, IconX } from "../Icons";
import { BandBadge, Meter } from "../Scores";

const BAND_CLASS = { "Strong fit": "fit-strong", "Partial fit": "fit-partial", "Weak fit": "fit-weak" } as const;

interface Props {
  rank: number;
  match: Match;
  onShortlist: (slug: string) => void;
}

export function MatchCard({ rank, match, onShortlist }: Props) {
  const { startup: s, criteria } = match;
  const band = matchBand(match);

  return (
    <article className="card match">
      <div className="match-rank tabular">{rank}</div>
      <div className="match-body">
        <div className="match-head">
          <div>
            <Link to={`/startups/${s.slug}`}>
              <strong>{s.name}</strong>
            </Link>
            <p className="small secondary">
              {s.sector} · {s.country} · {PIPELINE_LABELS[s.pipeline_stage]}
            </p>
          </div>
          <div className="match-score">
            <span className="value tabular">{match.score}</span>
            <span className={`badge ${BAND_CLASS[band]}`}>
              <span className="dot" aria-hidden />
              {band}
            </span>
          </div>
        </div>

        {criteria.length > 0 && (
          <ul className="criteria" aria-label="Thesis criteria">
            {criteria.map((c) => (
              <li key={c.key} className={c.met ? "met" : "missed"}>
                {c.met ? <IconCheck /> : <IconX />}
                <span className="visually-hidden">{c.met ? "Meets" : "Misses"}:</span>
                {c.label}
              </li>
            ))}
          </ul>
        )}

        <div className="match-foot">
          <div className="row-gap small secondary">
            Investment potential
            <Meter value={s.scores.potential} label="Investment potential" />
            <BandBadge band={s.scores.band} />
          </div>
          {s.pipeline_stage === "sourced" && (
            <button className="btn" type="button" onClick={() => onShortlist(s.slug)}>
              Move to screening
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
