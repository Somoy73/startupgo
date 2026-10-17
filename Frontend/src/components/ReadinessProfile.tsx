import { CircleHelp } from "lucide-react";
import type { LevelDetail } from "../api/backend-types";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";

/**
 * The six KTH IRL dimensions at their current level. What a level means is the KTH scale's
 * general definition (the same for every startup), so it sits behind a "?" hint.
 */
export function ReadinessProfile({
  levels,
  lagging,
}: {
  levels: LevelDetail[];
  lagging: string[];
}) {
  return (
    <div className="stack">
      {levels.map((l) => (
        <div key={l.dimension} className="readiness-row">
          <span className="inline-flex items-center gap-1">
            {l.dimension} · {l.name}
            <LevelHint level={l} />
            {lagging.includes(l.dimension) && <span className="small error"> · lagging</span>}
          </span>
          <progress aria-label={`${l.name} readiness`} max={9} value={l.level} />
          <strong>{l.level}/9</strong>
        </div>
      ))}
    </div>
  );
}

function LevelHint({ level: l }: { level: LevelDetail }) {
  return (
    <Popover>
      <PopoverTrigger
        className="inline-flex size-5 items-center justify-center rounded-full text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        aria-label={`What ${l.dimension} ${l.level} means`}
      >
        <CircleHelp aria-hidden className="size-3.5" />
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 text-sm">
        <p className="text-xs font-bold text-muted-foreground">KTH definition</p>
        <p className="mt-1">
          <strong>
            {l.dimension} {l.level}:
          </strong>{" "}
          {l.summary}
        </p>
        {l.next_summary && (
          <p className="mt-2 text-muted-foreground">
            <strong>
              Next, {l.dimension} {l.level + 1}:
            </strong>{" "}
            {l.next_summary}
          </p>
        )}
      </PopoverContent>
    </Popover>
  );
}
