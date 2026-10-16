/**
 * Smart search: turns a free-form query such as
 *   "seed kelp startups in europe with trl >= 6"
 * into structured filters, and back into a canonical query string.
 *
 * The query string is the single source of truth (it lives in the URL);
 * filters are always derived from it with `parseSearch`.
 */
import { DIMENSIONS, type DimensionKey, type PipelineStage, type StartupSummary } from "../api/types";
import { PIPELINE_LABELS, stageLabel } from "./format";
import { REGIONS, regionLabel, regionOf, type Region } from "./regions";

export interface SearchFilters {
  text: string[];
  stages: string[];
  sectors: string[];
  countries: string[];
  regions: Region[];
  impactAreas: string[];
  pipeline: PipelineStage[];
  minLevels: Partial<Record<DimensionKey, number>>;
}

/** Values that exist in the data, used to recognise sectors and countries in free text. */
export interface Vocabulary {
  sectors: string[];
  countries: string[];
}

export const emptyFilters = (): SearchFilters => ({
  text: [],
  stages: [],
  sectors: [],
  countries: [],
  regions: [],
  impactAreas: [],
  pipeline: [],
  minLevels: {},
});

export function vocabularyOf(startups: StartupSummary[]): Vocabulary {
  const unique = (values: string[]) => [...new Set(values)].sort();
  return { sectors: unique(startups.map((s) => s.sector)), countries: unique(startups.map((s) => s.country)) };
}

// ---------------------------------------------------------------------------
// Phrase tables (checked longest-first so "pre-seed" wins over "seed")
// ---------------------------------------------------------------------------

const STAGE_PHRASES: [string, RegExp][] = [
  ["pre-seed", /\bpre[- ]?seed\b/],
  ["seed", /\bseed\b/],
  ["series-a", /\bseries[- ]?a\b/],
  ["series-b", /\bseries[- ]?b\b/],
  ["series-c+", /\bseries[- ]?c\+?(?=\s|$)/],
  ["growth", /\bgrowth\b/],
  ["project-finance", /\bproject[- ]finance\b/],
];

const REGION_PHRASES: [Region, RegExp][] = [
  ["europe", /\beurop(e|ean)\b/],
  ["north-america", /\bnorth[- ]americ(a|an)\b/],
  ["latin-america", /\b(latin|south)[- ]americ(a|an)\b/],
  ["asia", /\basia(n)?\b/],
  ["africa", /\bafrica(n)?\b/],
  ["oceania", /\boceania\b/],
];

const COUNTRY_ALIASES: [string, RegExp][] = [
  ["United Kingdom", /\b(uk|britain|british)\b/],
  ["United States", /\b(usa|u\.s\.)(?=\s|$)/],
];

const AREA_PHRASES: [string, RegExp][] = [
  ["A", /\bocean resources\b/],
  ["B", /\bclean ocean\b/],
  ["C", /\bmarine habitats?\b/],
  ["D", /\b1\.5 ?c\b/],
  ["E", /\bcoastal (communities|resilience)\b/],
  ["F", /\bsocio[- ]economic\b/],
];

const PIPELINE_PHRASES: [PipelineStage, RegExp][] = [
  ["diligence", /\b(due )?diligence\b/],
  ["term-sheet", /\bterm[- ]sheets?\b/],
  ["screening", /\bscreening\b/],
  ["sourced", /\bsourced\b/],
  ["portfolio", /\bportfolio\b/],
  ["passed", /\bpassed\b/],
];

const LEVEL_PATTERN = /\b(crl|trl|brl|iprl|tmrl|frl)\s*(>=|≥|>|=|:)?\s*([1-9])\+?(?!\d)/g;
const KEY_VALUE_PATTERN = /\b(stage|sector|country|region|area|pipeline):(?:"([^"]+)"|(\S+))/g;

const STOP_WORDS = new Set(
  "a an and are at based companies company find for in is me of on or show stage startup startups that the with".split(
    " ",
  ),
);

const escapeRegExp = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const phrase = (value: string) => new RegExp(`(?<![\\w-])${escapeRegExp(value.toLowerCase())}(?![\\w-])`);
const addUnique = <T>(list: T[], value: T) => (list.includes(value) ? list : [...list, value]);

// ---------------------------------------------------------------------------
// Parse
// ---------------------------------------------------------------------------

export function parseSearch(input: string, vocab: Vocabulary): SearchFilters {
  const f = emptyFilters();
  let rest = ` ${input.toLowerCase()} `;

  // Removes every match of `pattern` from the remaining text, calling `onMatch` for each.
  const take = (pattern: RegExp, onMatch: (m: RegExpMatchArray) => void) => {
    const global = new RegExp(pattern.source, pattern.flags.includes("g") ? pattern.flags : pattern.flags + "g");
    rest = rest.replace(global, (...args) => {
      onMatch(args.slice(0, -2) as unknown as RegExpMatchArray);
      return " ";
    });
  };

  const findIn = (values: string[], raw: string) => values.find((v) => v.toLowerCase() === raw) ?? raw;

  take(KEY_VALUE_PATTERN, ([, key, quoted, bare]) => {
    const value = (quoted ?? bare).trim();
    switch (key) {
      case "stage":
        f.stages = addUnique(f.stages, value);
        break;
      case "sector":
        f.sectors = addUnique(f.sectors, findIn(vocab.sectors, value));
        break;
      case "country":
        f.countries = addUnique(f.countries, findIn(vocab.countries, value));
        break;
      case "region": {
        const region = REGIONS.find((r) => r.id === value || r.label.toLowerCase() === value);
        if (region) f.regions = addUnique(f.regions, region.id);
        break;
      }
      case "area":
        if (/^[a-f]$/.test(value)) f.impactAreas = addUnique(f.impactAreas, value.toUpperCase());
        break;
      case "pipeline": {
        const stage = PIPELINE_PHRASES.find(([id]) => id === value)?.[0];
        if (stage) f.pipeline = addUnique(f.pipeline, stage);
        break;
      }
    }
  });

  take(LEVEL_PATTERN, ([, dim, op, n]) => {
    const level = Math.min(9, Number(n) + (op === ">" ? 1 : 0));
    f.minLevels[dim as DimensionKey] = Math.max(f.minLevels[dim as DimensionKey] ?? 0, level);
  });

  // Multi-word vocabulary first, so "habitat restoration" is a sector, not two text terms.
  const bySpecificity = (values: string[]) => [...values].sort((a, b) => b.length - a.length);
  for (const sector of bySpecificity(vocab.sectors))
    take(phrase(sector), () => (f.sectors = addUnique(f.sectors, sector)));
  for (const country of bySpecificity(vocab.countries))
    take(phrase(country), () => (f.countries = addUnique(f.countries, country)));
  for (const [country, re] of COUNTRY_ALIASES) take(re, () => (f.countries = addUnique(f.countries, country)));
  for (const [stage, re] of STAGE_PHRASES) take(re, () => (f.stages = addUnique(f.stages, stage)));
  for (const [region, re] of REGION_PHRASES) take(re, () => (f.regions = addUnique(f.regions, region)));
  for (const [area, re] of AREA_PHRASES) take(re, () => (f.impactAreas = addUnique(f.impactAreas, area)));
  for (const [stage, re] of PIPELINE_PHRASES) take(re, () => (f.pipeline = addUnique(f.pipeline, stage)));

  f.text = rest
    .split(/[\s,;]+/)
    .map((t) => t.replace(/^[^\w]+|[^\w]+$/g, ""))
    .filter((t) => t && !STOP_WORDS.has(t))
    .reduce<string[]>(addUnique, []);

  return f;
}

// ---------------------------------------------------------------------------
// Format (canonical query string; parseSearch(formatSearch(f)) round-trips)
// ---------------------------------------------------------------------------

const quote = (v: string) => (/\s/.test(v) ? `"${v}"` : v);

export function formatSearch(f: SearchFilters): string {
  return [
    ...f.stages.map((v) => `stage:${v}`),
    ...f.sectors.map((v) => `sector:${quote(v)}`),
    ...f.countries.map((v) => `country:${quote(v)}`),
    ...f.regions.map((v) => `region:${v}`),
    ...f.impactAreas.map((v) => `area:${v}`),
    ...f.pipeline.map((v) => `pipeline:${v}`),
    ...DIMENSIONS.filter((d) => f.minLevels[d.key]).map((d) => `${d.key}>=${f.minLevels[d.key]}`),
    ...f.text,
  ].join(" ");
}

// ---------------------------------------------------------------------------
// Apply
// ---------------------------------------------------------------------------

export function matchesFilters(s: StartupSummary, f: SearchFilters): boolean {
  const anyOf = <T>(wanted: T[], actual: T | null) =>
    wanted.length === 0 || (actual !== null && wanted.includes(actual));
  const haystack = [s.name, s.tagline, s.description, s.sector, s.country, s.city ?? ""].join(" ").toLowerCase();

  return (
    f.text.every((t) => haystack.includes(t)) &&
    anyOf(f.stages, s.stage) &&
    anyOf(f.sectors, s.sector) &&
    anyOf(f.countries, s.country) &&
    anyOf(f.regions, regionOf(s.country)) &&
    anyOf(f.pipeline, s.pipeline_stage) &&
    (f.impactAreas.length === 0 || f.impactAreas.some((a) => s.scores.ocean_areas_covered.includes(a))) &&
    DIMENSIONS.every((d) => s.readiness[d.key] >= (f.minLevels[d.key] ?? 0))
  );
}

export const isEmpty = (f: SearchFilters) => formatSearch(f) === "";

// ---------------------------------------------------------------------------
// Chips: one removable label per active filter value
// ---------------------------------------------------------------------------

export interface FilterChip {
  id: string;
  label: string;
  without: SearchFilters;
}

export function filterChips(f: SearchFilters): FilterChip[] {
  const listChips = <K extends keyof Omit<SearchFilters, "minLevels">>(
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

  return [
    ...listChips("stages", "Stage: ", stageLabel),
    ...listChips("sectors", "Sector: ", (v) => v),
    ...listChips("countries", "Country: ", (v) => v),
    ...listChips("regions", "Region: ", regionLabel),
    ...listChips("impactAreas", "Impact area ", (v) => v),
    ...listChips("pipeline", "Pipeline: ", (v) => PIPELINE_LABELS[v]),
    ...levelChips,
    ...listChips("text", "", (v) => `“${v}”`),
  ];
}
