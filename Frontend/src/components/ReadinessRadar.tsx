import type { LevelDetail } from "../api/backend-types";
import { RadarChart } from "./RadarChart";

/** The six KTH IRL dimensions, scale 0-9. Lagging dimensions get a red point. */
export function ReadinessRadar({ levels, lagging }: { levels: LevelDetail[]; lagging: string[] }) {
  return (
    <RadarChart
      labels={levels.map((l) => l.dimension)}
      values={levels.map((l) => l.level)}
      max={9}
      step={3}
      ariaLabel={`Readiness levels out of 9: ${levels.map((l) => `${l.dimension} ${l.level}`).join(", ")}`}
      alerts={levels.map((l) => lagging.includes(l.dimension))}
      tooltip={(i) => ({
        title: levels[i] ? `${levels[i].dimension} · ${levels[i].name}` : "",
        label: `Level ${levels[i]?.level ?? 0} of 9`,
      })}
    />
  );
}
