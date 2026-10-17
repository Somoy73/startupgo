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

/** Up to n other startups like `picked`: same sector first, then the closest readiness index. */
export const similarStartups = (picked: RankedStartup, pool: RankedStartup[], n = 3): RankedStartup[] =>
  pool
    .filter((r) => r.startup.slug !== picked.startup.slug)
    .map((r) => ({ r, sector: r.startup.sector === picked.startup.sector ? 0 : 1, gap: Math.abs(r.total - picked.total) }))
    .sort((a, b) => a.sector - b.sector || a.gap - b.gap || a.r.startup.name.localeCompare(b.r.startup.name))
    .slice(0, n)
    .map(({ r }) => r);
