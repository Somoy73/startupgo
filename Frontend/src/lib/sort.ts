import { FUNDING_STAGES, PIPELINE_STAGES, type FundingStage, type StartupSummary } from "@/api/types";

export type SortDir = "asc" | "desc";
type Value = number | string | null;

interface SortDef {
  label: string;
  /** null: keep the order the search returned. */
  value: ((s: StartupSummary) => Value) | null;
  /** Direction on the first click: scores high-to-low, names A-Z. */
  defaultDir: SortDir;
}

/**
 * Deal-flow sort options. Sorting happens here, not on the backend, so changing the
 * order never re-runs a search.
 */
export const SORTS = {
  relevance: { label: "Relevance", value: null, defaultDir: "desc" },
  potential: { label: "Investment potential", value: (s) => s.scores.potential, defaultDir: "desc" },
  readiness: { label: "Readiness", value: (s) => s.scores.readiness, defaultDir: "desc" },
  ocean: { label: "Ocean impact", value: (s) => s.scores.ocean_impact, defaultDir: "desc" },
  momentum: { label: "Momentum", value: (s) => s.scores.momentum, defaultDir: "desc" },
  crl: { label: "CRL", value: (s) => s.readiness.crl, defaultDir: "desc" },
  trl: { label: "TRL", value: (s) => s.readiness.trl, defaultDir: "desc" },
  brl: { label: "BRL", value: (s) => s.readiness.brl, defaultDir: "desc" },
  iprl: { label: "IPRL", value: (s) => s.readiness.iprl, defaultDir: "desc" },
  tmrl: { label: "TMRL", value: (s) => s.readiness.tmrl, defaultDir: "desc" },
  frl: { label: "FRL", value: (s) => s.readiness.frl, defaultDir: "desc" },
  stage: { label: "Stage", value: (s) => ordinal(FUNDING_STAGES, s.stage as FundingStage), defaultDir: "desc" },
  funding: { label: "Disclosed funding", value: (s) => s.total_disclosed_usd, defaultDir: "desc" },
  lastRound: { label: "Last round", value: (s) => s.last_round_on, defaultDir: "desc" },
  pipeline: { label: "Pipeline", value: (s) => ordinal(PIPELINE_STAGES, s.pipeline_stage), defaultDir: "desc" },
  name: { label: "Name", value: (s) => s.name, defaultDir: "asc" },
} satisfies Record<string, SortDef>;

export type SortKey = keyof typeof SORTS;

export interface Sort {
  key: SortKey;
  dir: SortDir;
}

function ordinal<T>(order: readonly T[], value: T): number | null {
  const i = order.indexOf(value);
  return i < 0 ? null : i;
}

export const isSortKey = (v: string | null): v is SortKey => v !== null && v in SORTS;

/** Relevance while searching; potential when browsing everything (relevance means nothing there). */
export const defaultSort = (searching: boolean): Sort =>
  searching ? { key: "relevance", dir: "desc" } : { key: "potential", dir: "desc" };

export const isDefaultSort = (sort: Sort, searching: boolean) => {
  const d = defaultSort(searching);
  return sort.key === d.key && sort.dir === d.dir;
};

/** URL form: "potential" is ascending, "-potential" descending. */
export const formatSort = (sort: Sort) =>
  sort.key === "relevance" ? "relevance" : `${sort.dir === "desc" ? "-" : ""}${sort.key}`;

export function parseSort(param: string | null, searching: boolean): Sort {
  if (param) {
    const descending = param.startsWith("-");
    const key = descending ? param.slice(1) : param;
    if (isSortKey(key) && (key !== "relevance" || searching)) {
      return { key, dir: key === "relevance" || descending ? "desc" : "asc" };
    }
  }
  return defaultSort(searching);
}

/** Header click: the column's natural direction, then reversed, then back to the default order. */
export function nextSort(current: Sort, key: SortKey, searching: boolean): Sort {
  const natural = SORTS[key].defaultDir;
  if (current.key !== key) return { key, dir: natural };
  if (current.dir === natural) return { key, dir: natural === "asc" ? "desc" : "asc" };
  return defaultSort(searching);
}

/** Stable sort; missing values always go last, whichever the direction. */
export function sortStartups(list: StartupSummary[], sort: Sort): StartupSummary[] {
  const value: SortDef["value"] = SORTS[sort.key].value;
  if (!value) return [...list];
  const sign = sort.dir === "asc" ? 1 : -1;
  return [...list].sort((a, b) => {
    const x = value(a);
    const y = value(b);
    if (x === null || y === null) return x === y ? 0 : x === null ? 1 : -1;
    const order = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    return sign * order;
  });
}
