/**
 * Discover filters: chips, their URL encoding and matching.
 *
 * What the user types goes to the search (api.searchStartups). Filters (`f` in the URL,
 * e.g. `stage:seed region:Europe trl>=6`, written by `formatSearch` and read back by
 * `parseSearch`) refine whatever is listed, here in the browser with `matchesFilters`.
 */
import { DIMENSIONS, PIPELINE_STAGES, type DimensionKey, type PipelineStage, type StartupSummary } from "../api/types";
import { PIPELINE_LABELS, stageLabel } from "./format";
import { REGIONS } from "./regions";

export type SearchFilters = {
  /** Every term must appear. */
  text: string[];
  /** At least one term must appear (written `any:term`). */
  anyText: string[];
  stages: string[];
  sectors: string[];
  countries: string[];
  /** Region names as on each startup (`region` field), e.g. "Europe". */
  regions: string[];
  impactAreas: string[];
  pipeline: PipelineStage[];
  minLevels: Partial<Record<DimensionKey, number>>;
};

export const emptyFilters = (): SearchFilters => ({
  text: [],
  anyText: [],
  stages: [],
  sectors: [],
  countries: [],
  regions: [],
  impactAreas: [],
  pipeline: [],
  minLevels: {},
});

const addUnique = <T>(list: T[], value: T) => (list.includes(value) ? list : [...list, value]);
const quote = (v: string) => (/\s/.test(v) ? `"${v}"` : v);

// URL keys for the readiness dimensions: the KTH codes, e.g. "iprl" for `ipr`.
const LEVEL_KEY = Object.fromEntries(DIMENSIONS.map((d) => [d.code.toLowerCase(), d.key])) as Record<
  string,
  DimensionKey
>;
const KEY_VALUE = /(stage|sector|country|region|area|pipeline|any):(?:"([^"]+)"|(\S+))/g;
const LEVEL = /\b([a-z]+)>=([1-9])\b/g;

// ---------------------------------------------------------------------------
// URL encoding (formatSearch writes it, parseSearch reads it back)
// ---------------------------------------------------------------------------

export function formatSearch(f: SearchFilters): string {
  return [
    ...f.stages.map((v) => `stage:${v}`),
    ...f.sectors.map((v) => `sector:${quote(v)}`),
    ...f.countries.map((v) => `country:${quote(v)}`),
    ...f.regions.map((v) => `region:${quote(v)}`),
    ...f.impactAreas.map((v) => `area:${v}`),
    ...f.pipeline.map((v) => `pipeline:${v}`),
    ...DIMENSIONS.filter((d) => f.minLevels[d.key]).map((d) => `${d.code.toLowerCase()}>=${f.minLevels[d.key]}`),
    ...f.anyText.map((v) => `any:${quote(v)}`),
    ...f.text,
  ].join(" ");
}

export function parseSearch(input: string): SearchFilters {
  const f = emptyFilters();
  let rest = input.replace(KEY_VALUE, (_, key: string, quoted?: string, bare?: string) => {
    const value = (quoted ?? bare ?? "").trim();
    if (!value) return " ";
    if (key === "stage") f.stages = addUnique(f.stages, value);
    else if (key === "sector") f.sectors = addUnique(f.sectors, value);
    else if (key === "country") f.countries = addUnique(f.countries, value);
    else if (key === "region") f.regions = addUnique(f.regions, value);
    else if (key === "area") f.impactAreas = addUnique(f.impactAreas, value.toUpperCase());
    else if (key === "pipeline" && (PIPELINE_STAGES as readonly string[]).includes(value))
      f.pipeline = addUnique(f.pipeline, value as PipelineStage);
    else if (key === "any") f.anyText = addUnique(f.anyText, value.toLowerCase());
    return " ";
  });
  rest = rest.replace(LEVEL, (match, code: string, level: string) => {
    const key = LEVEL_KEY[code];
    if (!key) return match;
    f.minLevels[key] = Number(level);
    return " ";
  });
  f.text = rest.toLowerCase().split(/\s+/).filter(Boolean).reduce<string[]>(addUnique, []);
  return f;
}

export const isEmpty = (f: SearchFilters) => formatSearch(f) === "";

// ---------------------------------------------------------------------------
// Matching
// ---------------------------------------------------------------------------

const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();

/** Facets AND together; values within a facet OR. */
export function matchesFilters(s: StartupSummary, f: SearchFilters): boolean {
  const haystack = [s.name, s.tagline, s.description, s.sector, s.country, s.region, s.city].join(" ").toLowerCase();
  const anyOf = <T>(wanted: T[], test: (w: T) => boolean) => wanted.length === 0 || wanted.some(test);

  return (
    f.text.every((t) => haystack.includes(t)) &&
    anyOf(f.anyText, (t) => haystack.includes(t)) &&
    anyOf(f.stages, (v) => v === s.stage) &&
    anyOf(f.sectors, (v) => same(v, s.sector)) &&
    anyOf(f.countries, (v) => same(v, s.country)) &&
    anyOf(f.regions, (v) => same(v, s.region)) &&
    anyOf(f.pipeline, (p) => p === s.pipeline_stage) &&
    anyOf(f.impactAreas, (a) => s.scores.ocean_areas_covered.includes(a)) &&
    DIMENSIONS.every((d) => s.readiness[d.key] >= (f.minLevels[d.key] ?? 0))
  );
}

// ---------------------------------------------------------------------------
// Chips: one removable label per active filter value
// ---------------------------------------------------------------------------

export type FilterChip = { id: string; label: string; without: SearchFilters };

export function filterChips(f: SearchFilters): FilterChip[] {
  const listChips = <K extends Exclude<keyof SearchFilters, "minLevels">>(
    key: K,
    prefix: string,
    label: (v: SearchFilters[K][number]) => string,
  ): FilterChip[] =>
    (f[key] as SearchFilters[K][number][]).map((value) => ({
      id: `${key}:${value}`,
      label: `${prefix}${label(value)}`,
      without: { ...f, [key]: (f[key] as unknown[]).filter((v) => v !== value) },
    }));

  const levelChips = DIMENSIONS.filter((d) => f.minLevels[d.key]).map((d) => {
    const minLevels = { ...f.minLevels };
    delete minLevels[d.key];
    return { id: `level:${d.key}`, label: `${d.code} ≥ ${f.minLevels[d.key]}`, without: { ...f, minLevels } };
  });

  const regionLabel = (v: string) => REGIONS.find((r) => same(r.id, v))?.label ?? v;

  return [
    ...listChips("stages", "Stage: ", stageLabel),
    ...listChips("sectors", "Sector: ", (v) => v),
    ...listChips("countries", "Country: ", (v) => v),
    ...listChips("regions", "Region: ", regionLabel),
    ...listChips("impactAreas", "Impact area ", (v) => v),
    ...listChips("pipeline", "Pipeline: ", (v) => PIPELINE_LABELS[v]),
    ...levelChips,
    ...listChips("anyText", "Any: ", (v) => `“${v}”`),
    ...listChips("text", "", (v) => `“${v}”`),
  ];
}
