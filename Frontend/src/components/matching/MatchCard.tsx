import { Link } from "react-router-dom";
import { LuCheck, LuX } from "react-icons/lu";
import { PIPELINE_LABELS } from "@/lib/format";
import { matchBand, type Match } from "@/lib/matching";
import { badge, BandBadge, button, card, cx, Meter, row } from "@/components/ui";

const FIT_DOT = { "Strong fit": "bg-good", "Partial fit": "bg-warning", "Weak fit": "bg-muted" } as const;

interface Props {
  rank: number;
  match: Match;
  onShortlist: (slug: string) => void;
}

export function MatchCard({ rank, match, onShortlist }: Props) {
  const { startup: s, criteria } = match;
  const band = matchBand(match);

  return (
    <article className={cx(card, "grid grid-cols-[36px_minmax(0,1fr)] gap-1 py-3.5 pr-4 pl-2")}>
      <div className="pt-0.5 text-center font-bold text-muted tabular-nums">{rank}</div>
      <div className="flex flex-col gap-2.5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <Link to={`/startups/${s.slug}`}>
              <strong>{s.name}</strong>
            </Link>
            <p className="text-small text-fg-2">
              {s.sector} · {s.country} · {PIPELINE_LABELS[s.pipeline_stage]}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <span className="text-h1 leading-none font-bold tabular-nums">{match.score}</span>
            <span className={badge}>
              <span className={cx("size-2 rounded-full", FIT_DOT[band])} aria-hidden />
              {band}
            </span>
          </div>
        </div>

        {criteria.length > 0 && (
          <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0" aria-label="Thesis criteria">
            {criteria.map((c) => (
              <li
                key={c.key}
                className="inline-flex items-center gap-1 rounded-md bg-surface-2 px-2 py-0.5 text-sm text-fg-2"
              >
                {c.met ? <LuCheck size={14} className="text-good" /> : <LuX size={14} className="text-critical" />}
                <span className="sr-only">{c.met ? "Meets" : "Misses"}:</span>
                {c.label}
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className={cx(row, "text-small text-fg-2")}>
            Investment potential
            <Meter value={s.scores.potential} label="Investment potential" />
            <BandBadge band={s.scores.band} />
          </div>
          {s.pipeline_stage === "sourced" && (
            <button className={button()} type="button" onClick={() => onShortlist(s.slug)}>
              Move to screening
            </button>
          )}
        </div>
      </div>
    </article>
  );
}
