import type { StartupSummary } from "../api/backend-types";

export type RankedStartup = {
  startup: StartupSummary;
  /** The readiness index (0-100) from the database; the rank and the graph score. */
  total: number;
  readiness: number;
  impact: number;
  potential: number;
};

/** The assessed startups with the highest readiness index first (ties by name). Unassessed ones have no score and are left out. */
export const rankByReadiness = (startups: StartupSummary[], n = 10): RankedStartup[] =>
  startups
    .filter((s) => s.assessed)
    .map((startup) => ({
      startup,
      total: Math.round(startup.scores.readiness),
      readiness: Math.round(startup.scores.readiness),
      impact: Math.round(startup.scores.ocean_impact),
      potential: Math.round(startup.scores.potential),
    }))
    .sort((a, b) => b.startup.scores.readiness - a.startup.scores.readiness || a.startup.name.localeCompare(b.startup.name))
    .slice(0, n);
