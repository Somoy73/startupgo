import type { StartupSummary } from "../api/types";

type Comparator = (a: StartupSummary, b: StartupSummary) => number;

const desc =
  (value: (s: StartupSummary) => number): Comparator =>
  (a, b) =>
    value(b) - value(a);

export const SORTS = {
  potential: { label: "Investment potential", compare: desc((s) => s.scores.potential) },
  readiness: { label: "Readiness", compare: desc((s) => s.scores.readiness) },
  ocean: { label: "Ocean impact", compare: desc((s) => s.scores.ocean_impact) },
  momentum: { label: "Momentum", compare: desc((s) => s.scores.momentum) },
  trl: { label: "TRL", compare: desc((s) => s.readiness.trl) },
  brl: { label: "BRL", compare: desc((s) => s.readiness.brl) },
  name: { label: "Name", compare: (a, b) => a.name.localeCompare(b.name) },
} satisfies Record<string, { label: string; compare: Comparator }>;

export type SortKey = keyof typeof SORTS;

export const isSortKey = (v: string | null): v is SortKey => v !== null && v in SORTS;

export function sortStartups(list: StartupSummary[], key: SortKey): StartupSummary[] {
  return [...list].sort(SORTS[key].compare);
}
