import { Link } from "@tanstack/react-router";
import type { InvestorMatch } from "../../lib/investor";

type Props = {
  matches: InvestorMatch[];
  hovered: string | null;
  onHover: (slug: string | null) => void;
};

export function TopMatchList({ matches, hovered, onHover }: Props) {
  return (
    <ol className="tm-list">
      {matches.map((m, i) => (
        <li key={m.startup.slug} style={{ ["--i" as string]: i }}>
          <Link
            to="/startups/$slug"
            params={{ slug: m.startup.slug }}
            className={`tm-row${i < 3 ? " is-top" : ""}${hovered === m.startup.slug ? " is-hover" : ""}`}
            onMouseEnter={() => onHover(m.startup.slug)}
            onMouseLeave={() => onHover(null)}
            onFocus={() => onHover(m.startup.slug)}
            onBlur={() => onHover(null)}
          >
            <span className="tm-badge" aria-hidden>
              {m.startup.name[0]}
            </span>
            <span className="tm-text">
              <strong>{m.startup.name}</strong>
              <small>
                Fit {m.thesis} · Readiness {m.readiness} · Impact {m.impact}
              </small>
            </span>
            <span className="tm-score">{m.total}</span>
          </Link>
        </li>
      ))}
    </ol>
  );
}
