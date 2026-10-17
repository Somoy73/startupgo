import { queryOptions } from "@tanstack/react-query";
import { backend } from "../api/backend";
import {
  BACKEND_PIPELINE_STAGES,
  KTH_DIMENSIONS,
  type BackendPipelineStage,
  type KthKey,
  type SearchMatch,
  type StartupSummary,
} from "../api/backend-types";

export type SearchFilters = {
  stages: string[];
  countries: string[];
  sectors: string[];
  impactAreas: string[];
  pipeline: BackendPipelineStage[];
  minLevels: Partial<Record<KthKey, number>>;
};
export const emptyFilters = (): SearchFilters => ({ stages: [], countries: [], sectors: [], impactAreas: [], pipeline: [], minLevels: {} });
export function parseFilters(value: unknown): SearchFilters {
  const empty = emptyFilters();
  try {
    const parsed = typeof value === "string" ? JSON.parse(value) : value;
    if (!parsed || typeof parsed !== "object") return empty;
    for (const key of ["stages", "countries", "sectors", "impactAreas"] as const) {
      empty[key] = Array.isArray(parsed[key]) ? parsed[key].filter((item: unknown) => typeof item === "string") : [];
    }
    empty.pipeline = Array.isArray(parsed.pipeline) ? parsed.pipeline.filter((item: unknown): item is BackendPipelineStage => BACKEND_PIPELINE_STAGES.some((stage) => stage === item)) : [];
    for (const d of KTH_DIMENSIONS) {
      const level = parsed.minLevels?.[d.key];
      if (Number.isInteger(level) && level >= 1 && level <= 9) empty.minLevels[d.key] = level;
    }
  } catch { /* Invalid old links use default filters. */ }
  return empty;
}
export function filterStartups<T extends StartupSummary>(items: T[], filters: SearchFilters): T[] {
  return items.filter((s) =>
    (!filters.stages.length || filters.stages.includes(s.stage)) &&
    (!filters.countries.length || filters.countries.includes(s.country)) &&
    (!filters.sectors.length || filters.sectors.includes(s.sector)) &&
    (!filters.pipeline.length || filters.pipeline.includes(s.pipeline_stage)) &&
    (!filters.impactAreas.length || filters.impactAreas.some((area) => s.scores.ocean_areas_covered.includes(area))) &&
    KTH_DIMENSIONS.every((d) => s.readiness[d.key] >= (filters.minLevels[d.key] ?? 0)),
  );
}
export type SearchSortKey = "relevance" | "name" | "stage" | KthKey | "readiness" | "ocean" | "momentum" | "potential" | "funding" | "lastRound" | "pipeline";
export type SearchSort = { key: SearchSortKey; direction: "asc" | "desc" };
export function parseSearchSort(value: unknown, query: string): SearchSort {
  const keys: SearchSortKey[] = ["relevance", "name", "stage", "readiness", "ocean", "momentum", "potential", "funding", "lastRound", "pipeline", ...KTH_DIMENSIONS.map((d) => d.key)];
  const [key, direction] = typeof value === "string" ? value.split(":") : [];
  const known = keys.find((candidate) => candidate === key);
  return { key: known ?? (query ? "relevance" : "potential"), direction: direction === "asc" ? "asc" : "desc" };
}
export function sortSearchResults<T extends StartupSummary>(items: T[], sort: SearchSort): T[] {
  const value = (s: T): number | string => {
    if (sort.key === "relevance") return (s as T & Partial<SearchMatch>).relevance ?? 0;
    if (sort.key === "name" || sort.key === "stage") return s[sort.key];
    if (sort.key === "pipeline") return s.pipeline_stage;
    if (sort.key === "funding") return s.total_disclosed_usd ?? 0;
    if (sort.key === "lastRound") return s.last_round_on ?? "";
    if (sort.key === "ocean") return s.scores.ocean_impact;
    if (sort.key === "potential" || sort.key === "readiness" || sort.key === "momentum") return s.scores[sort.key];
    return s.readiness[sort.key];
  };
  return [...items].sort((a, b) => {
    const x = value(a), y = value(b);
    const comparison = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
    return (sort.direction === "asc" ? comparison : -comparison) || a.name.localeCompare(b.name);
  });
}
export const startupListOptions = queryOptions({ queryKey: ["discover", "startups"], queryFn: () => backend.startups() });
export const frameworksOptions = queryOptions({ queryKey: ["discover", "frameworks"], queryFn: () => backend.frameworks(), staleTime: Infinity });
