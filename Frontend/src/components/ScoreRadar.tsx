import { useId, useState } from "react";
import type { Scores } from "../api/backend-types";
import { score } from "../lib/format";
import { cn } from "../lib/utils";
import { DetailsToggle } from "./DetailsToggle";
import { RadarChart } from "./RadarChart";

/**
 * The Scores box: the three scores investment potential is made of (0-100), as a radar. "Show numbers" (top right)
 * expands each score and what it's made of on the right of the chart.
 */
export function ScoreRadar({
  scores,
  lastRound,
  className,
}: {
  scores: Scores;
  lastRound: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const numbersId = useId();
  const metrics = [
    {
      label: "Readiness",
      name: "Readiness index (KTH IRL)",
      value: scores.readiness,
      note: `Spread ${scores.readiness_spread} levels across dimensions`,
    },
    {
      label: "Ocean impact",
      name: "Ocean impact readiness",
      value: scores.ocean_impact,
      note: `Best evidence: ${scores.ocean_evidence_label} · areas ${scores.ocean_areas_covered.join(", ") || "none"}`,
    },
    {
      label: "Momentum",
      name: "Funding momentum",
      value: scores.momentum,
      note: `Last round ${lastRound}`,
    },
  ];

  return (
    <section className={cn("card card-pad", className)}>
      <div className="card-head">
        <h2>Scores</h2>
        <DetailsToggle
          open={open}
          onToggle={() => setOpen((o) => !o)}
          controls={numbersId}
          showLabel="Show numbers"
          hideLabel="Hide numbers"
        />
      </div>
      <div className={cn("grid grid-cols-1 items-center gap-6", open && "sm:grid-cols-2")}>
        <RadarChart
          labels={metrics.map((m) => m.label)}
          values={metrics.map((m) => m.value)}
          max={100}
          step={25}
          ariaLabel={`Scores out of 100: ${metrics.map((m) => `${m.name} ${score(m.value)}`).join(", ")}`}
          tooltip={(i) => ({
            title: metrics[i]?.name ?? "",
            label: `${score(metrics[i]?.value ?? 0)} of 100`,
          })}
        />
        <dl id={numbersId} hidden={!open} className="stack" style={{ gap: 14 }}>
          {metrics.map((m) => (
            <div key={m.name}>
              <dt className="small muted">{m.name}</dt>
              <dd className="text-2xl font-bold text-primary tabular-nums">{score(m.value)}</dd>
              <dd className="small muted">{m.note}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
