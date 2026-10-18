import type { Scores } from "../api/backend-types";
import { score } from "../lib/format";
import { cn } from "../lib/utils";
import { useCountUp } from "../lib/useCountUp";

function getScoreStyle(val: number) {
  if (val < 30) return "bg-red-500/20 text-red-400 border-red-500/50";
  if (val < 50) return "bg-orange-500/20 text-orange-300 border-orange-500/50";
  if (val < 70) return "bg-yellow-500/20 text-yellow-300 border-yellow-500/50";
  if (val >= 70) return "bg-emerald-500/20 text-emerald-300 border-emerald-500/50";
  // Fallback for null
  return "bg-sky-500/20 text-sky-300 border-sky-500/50";
}

/** Investment potential (0–100) badge with color-coded score */
export function PotentialMark({ scores }: { scores: Scores }) {
  const value = score(scores.potential);
  const shown = Math.round(useCountUp(value));

return (
    <div className="flex flex-col items-center gap-2 text-center">
      <div
        className={cn(
          // grid place-items-center + leading-none gives true vertical & horizontal centering
          "mark-in grid size-32 place-items-center rounded-full border-2 text-center shadow-lg backdrop-blur-sm",
          getScoreStyle(value),
        )}
      >
        <span
          className="font-display text-5xl font-bold leading-none tabular-nums select-none"
          aria-label={`${value}`}
        >
          {shown}
        </span>
      </div>
      <span
        className="text-xs font-semibold tracking-wider uppercase opacity-80"
        title="Weights are provisional; see RESEARCH.md section 2.5"
      >
        Investment potential
      </span>
      {scores.potential_coverage !== undefined && scores.potential_coverage < 1 && (
        <span className="text-xs opacity-70">
          Partial data: {Math.round(scores.potential_coverage * 100)}% of inputs
        </span>
      )}
    </div>
  );
}
