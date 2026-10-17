import type { StartupSummary } from "../api/types";
export const SORTS = {
  potential: { label: "Investment potential" },
  impact: { label: "Ocean impact" },
  trl: { label: "TRL" },
  funding: { label: "Disclosed funding" },
};
export type SortKey = keyof typeof SORTS;
export const isSortKey = (v: string | null): v is SortKey => v !== null && v in SORTS;
export const sortStartups = (s: StartupSummary[], k: SortKey) =>
  [...s].sort((a, b) => {
    const value = (s: StartupSummary) =>
      k === "potential"
        ? s.scores.potential
        : k === "impact"
          ? s.scores.ocean_impact
          : k === "trl"
            ? s.readiness.trl
            : s.total_disclosed_usd;
    return value(b) - value(a);
  });
