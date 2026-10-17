import { layoutNodes } from "../../lib/match-graph";
import type { RankedStartup } from "../../lib/readiness-ranking";

const SIZE = 360;

type Props = {
  matches: RankedStartup[];
  hovered: string | null;
  selected: string | null;
  onHover: (slug: string | null) => void;
  onSelect: (slug: string) => void };

export function MatchRadar({ matches, hovered, selected, onHover, onSelect }: Props) {
  const nodes = layoutNodes(matches.map((m) => ({ slug: m.startup.slug, score: m.total })), SIZE);
  const c = SIZE / 2;
  // Reveal order: weaker matches first, top matches last.
  const order = (i: number) => nodes.length - 1 - i;
  return (
    <svg
      className="match-radar"
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      role="img"
      aria-label="Top 5 startup matches around the investor"
    >
      {[0.16, 0.25, 0.34, 0.44].map((r, i) => (
        <circle
          key={r}
          className="mr-ring"
          cx={c}
          cy={c}
          r={SIZE * r}
          style={{ ["--i" as string]: i }}
        />
      ))}
      {nodes.map((n, i) => {
        const len = Math.hypot(n.x - c, n.y - c);
        return (
          <line
            key={`l-${n.slug}`}
            className={`mr-line${n.highlighted ? " is-top" : ""}${hovered === n.slug ? " is-hover" : ""}`}
            x1={c}
            y1={c}
            x2={n.x}
            y2={n.y}
            style={{ ["--i" as string]: order(i), ["--len" as string]: len }}
          />
        );
      })}
      <circle className="mr-center-glow" cx={c} cy={c} r={20} />
      <circle className="mr-center" cx={c} cy={c} r={10} />
      {nodes.map((n, i) => {
        const m = matches[i]!;
        return (
          <g
            key={n.slug}
            role="button"
            tabIndex={0}
            aria-pressed={selected === n.slug}
            onClick={() => onSelect(n.slug)}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(n.slug); } }}
            aria-label={`${m.startup.name}, score ${m.total}`}
            onMouseEnter={() => onHover(n.slug)}
            onMouseLeave={() => onHover(null)}
            onFocus={() => onHover(n.slug)}
            onBlur={() => onHover(null)}
          >
            <g
              className={`mr-node${n.highlighted ? " is-top" : ""}${hovered === n.slug || selected === n.slug ? " is-hover" : ""}`}
              style={{ ["--i" as string]: order(i), transformOrigin: `${n.x}px ${n.y}px` }}
            >
              <circle className="mr-halo" cx={n.x} cy={n.y} r={14} />
              <circle className="mr-dot" cx={n.x} cy={n.y} r={n.highlighted ? 8 : 6} />
              {n.highlighted && (
                <text className="mr-label" x={n.x + 13} y={n.y + 4}>
                  {n.score}
                </text>
              )}
            </g>
          </g>
        );
      })}
    </svg>
  );
}
