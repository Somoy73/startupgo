import type { Scores } from "../api/backend-types";
import { score } from "../lib/format";
import { cn } from "../lib/utils";

// Ring and number colour by band, like a grade circled in coloured pen.
const BAND_INK: Record<string, string> = {
  Strong: "border-success text-success",
  Promising: "border-ocean text-ocean",
  Watch: "border-amber-600 text-amber-600",
  Early: "border-destructive text-destructive",
};

/** Investment potential (0-100) as a circled grade, coloured by its band. */
export function PotentialMark({ scores }: { scores: Scores }) {
  const value = score(scores.potential);
  const penalty =
    scores.imbalance_penalty > 0
      ? ` · includes −${scores.imbalance_penalty} imbalance penalty`
      : "";

  return (
    <div className="flex flex-col items-center gap-2 text-center">
      <div
        role="img"
        aria-label={`Investment potential ${value} out of 100, ${scores.band}${penalty}`}
        className={cn(
          "flex size-40 items-center justify-center rounded-full border-[6px] bg-white shadow-card",
          BAND_INK[scores.band] ?? "border-ocean text-ocean",
        )}
      >
        <span className="flex items-baseline">
          <span className="font-display text-6xl leading-none font-bold tabular-nums">{value}</span>
          <span className="ml-0.5 text-base font-semibold opacity-70">/100</span>
        </span>
      </div>
      <span className="text-xs font-bold tracking-wide uppercase">Investment potential</span>
      {scores.imbalance_penalty > 0 && (
        <span className="text-xs opacity-80">
          Includes −{scores.imbalance_penalty} imbalance penalty
        </span>
      )}
    </div>
  );
}
