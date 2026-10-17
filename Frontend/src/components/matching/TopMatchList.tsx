import type { RankedStartup } from "../../lib/readiness-ranking";

type Props = {
  matches: RankedStartup[];
  hovered: string | null;
  selected: string | null;
  onHover: (slug: string | null) => void;
  onSelect: (slug: string) => void
};

export function TopMatchList({ matches, hovered, selected, onHover, onSelect }: Props) {
  return (
    <ol className="tm-list">
      {matches.map((m, i) => (
        <li key={m.startup.slug} style={{ ["--i" as string]: i }}>
          <button
            type="button"
            aria-pressed={selected === m.startup.slug}
            onClick={() => onSelect(m.startup.slug)}
            className={`tm-row${i < 3 ? " is-top" : ""}${hovered === m.startup.slug || selected === m.startup.slug ? " is-hover" : ""}`}
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
                Readiness {m.readiness} · Impact {m.impact} · Potential {m.potential}
              </small>
            </span>
            <span className="tm-score">{m.total}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}
