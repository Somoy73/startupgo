/**
 * Search filters on the client: chips, and the URL encoding of edited filters.
 *
 * Interpretation and filtering happen on the backend (POST /api/search). The URL holds
 * either `q` (what the user typed) or, once they edit a chip or a
 * dropdown, `f`: the filters as a canonical string such as
 *   stage:seed region:nordics trl>=6 any:kelp
 * written by `formatSearch` and read back by `parseSearch`.
 */
import {
  DIMENSIONS,
  type ApiSearchFilters,
  type DimensionKey,
  type PipelineStage,
  type StartupSummary,
} from "@/api/types";
import { PIPELINE_LABELS, stageLabel } from "./format";
import { REGIONS, regionLabel, type Region } from "./regions";

export interface SearchFilters {
  /** Every term must appear. */
  text: string[];
  /** At least one term must appear (synonyms from smart search, written `any:term`). */
  anyText: string[];
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
  anyText: [],
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
  ["nordics", /\b(nordics?|scandinavia(n)?)\b/],
  ["baltics", /\bbaltics?\b/],
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
const KEY_VALUE_PATTERN = /\b(stage|sector|country|region|area|pipeline|any):(?:"([^"]+)"|(\S+))/g;

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
      case "any":
        f.anyText = addUnique(f.anyText, value);
        break;
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
    ...f.anyText.map((v) => `any:${quote(v)}`),
    ...f.text,
  ].join(" ");
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

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
    ...listChips("anyText", "Any: ", (v) => `“${v}”`),
    ...listChips("text", "", (v) => `“${v}”`),
  ];
}

// ---------------------------------------------------------------------------
// Wire format (POST /api/search)
// ---------------------------------------------------------------------------

const REGION_IDS = new Set<string>(REGIONS.map((r) => r.id));
const PIPELINE_IDS = new Set<string>(PIPELINE_PHRASES.map(([id]) => id));

export function toApiFilters(f: SearchFilters): ApiSearchFilters {
  const min_levels = Object.fromEntries(DIMENSIONS.map(({ key }) => [key, f.minLevels[key] ?? 0])) as Record<
    DimensionKey,
    number
  >;
  return {
    stages: f.stages,
    sectors: f.sectors,
    countries: f.countries,
    regions: f.regions,
    impact_areas: f.impactAreas,
    pipeline: f.pipeline,
    min_levels,
    keywords: f.text,
    any_keywords: f.anyText,
  };
}

/** The backend's filters as UI filters, dropping anything the UI doesn't know. */
export function fromApiFilters(api: ApiSearchFilters): SearchFilters {
  const unique = <T>(values: T[]) => [...new Set(values)];
  const minLevels: SearchFilters["minLevels"] = {};
  for (const { key } of DIMENSIONS) {
    const level = Math.round(api.min_levels[key] ?? 0);
    if (level >= 1 && level <= 9) minLevels[key] = level;
  }
  return {
    text: unique(api.keywords.map((t) => t.toLowerCase().trim()).filter(Boolean)),
    anyText: unique(api.any_keywords.map((t) => t.toLowerCase().trim()).filter(Boolean)),
    stages: unique(api.stages),
    sectors: unique(api.sectors),
    countries: unique(api.countries),
    regions: unique(api.regions.filter((r): r is Region => REGION_IDS.has(r))),
    impactAreas: unique(api.impact_areas.map((a) => a.toUpperCase()).filter((a) => /^[A-F]$/.test(a))),
    pipeline: unique(api.pipeline.filter((p): p is PipelineStage => PIPELINE_IDS.has(p))),
    minLevels,
  };
}
