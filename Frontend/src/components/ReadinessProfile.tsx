import type { LevelDetail } from "@/api/types";
import { cx } from "@/components/ui";

interface Props {
  levels: LevelDetail[];
  lagging: string[];
}

/** Six KTH IRL dimensions as segmented 1-9 bars, with the current and next level text. */
export function ReadinessProfile({ levels, lagging }: Props) {
  return (
    <div className="flex flex-col gap-3.5">
      <div className="grid grid-cols-[120px_1fr] gap-3.5 text-2xs text-muted max-sm:grid-cols-1" aria-hidden>
        <div className="max-sm:hidden" />
        <div className="grid grid-cols-9 text-center">
          {Array.from({ length: 9 }, (_, i) => (
            <span key={i}>{i + 1}</span>
          ))}
        </div>
      </div>
      {levels.map((l) => {
        const isLagging = lagging.includes(l.dimension);
        return (
          <div
            className="grid grid-cols-[120px_1fr] items-center gap-x-3.5 gap-y-1.5 max-sm:grid-cols-1"
            key={l.dimension}
          >
            <div className="flex flex-col">
              <strong className="text-md">{l.dimension}</strong>
              <span className="text-label text-muted">{l.name}</span>
            </div>
            <div
              className="relative grid h-5 grid-cols-9 gap-0.5"
              role="img"
              aria-label={`${l.name} readiness level ${l.level} of 9${isLagging ? ", lagging" : ""}`}
              title={`${l.dimension} ${l.level}/9: ${l.summary}`}
            >
              {Array.from({ length: 9 }, (_, i) => (
                <div
                  key={i}
                  className={cx(
                    "first:rounded-l-sm last:rounded-r-sm",
                    i === l.level - 1 && "rounded-r-sm",
                    i >= l.level ? "bg-track opacity-45" : isLagging ? "bg-serious" : "bg-accent",
                  )}
                />
              ))}
            </div>
            <p className="col-start-2 text-small text-fg-2 max-sm:col-start-1">
              <strong className="tabular-nums">L{l.level}</strong> {l.summary}
              {isLagging && <strong> · Lagging: 3+ levels below the median</strong>}
              {l.next_summary && (
                <span className="text-muted">
                  {" "}
                  Next (L{l.level + 1}): {l.next_summary}
                </span>
              )}
            </p>
          </div>
        );
      })}
    </div>
  );
}
