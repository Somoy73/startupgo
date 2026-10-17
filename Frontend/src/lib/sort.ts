import type { StartupSummary } from "../api/types";

type Comparator = (a: StartupSummary, b: StartupSummary) => number;

const desc =
  (value: (s: StartupSummary) => number): Comparator =>
  (a, b) =>
    value(b) - value(a);

/**
 * Deal-flow sort options. Sorting happens here, not on the backend, so changing the
 * order never re-runs a search.
 */
export const SORTS = {
  // Keeps the order the search returned (best match first); Array#sort is stable.
  relevance: { label: "Relevance", compare: () => 0 },
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

/**
 * The sort to apply. Relevance only means something for search results, so it is the
 * default while searching and unavailable when browsing everything.
 */
export function effectiveSort(requested: string | null, searching: boolean): SortKey {
  if (isSortKey(requested) && (requested !== "relevance" || searching)) return requested;
  return searching ? "relevance" : "potential";
}

export function sortStartups(list: StartupSummary[], key: SortKey): StartupSummary[] {
  return [...list].sort(SORTS[key].compare);
}
