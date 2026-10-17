import type { StartupSummary } from "../api/types";
export type SearchFilters = {
  text: string;
  sectors: string[];
  regions: string[];
  impactAreas: string[];
};
export function parseSearch(q: string, _v: unknown): SearchFilters {
  const values = (key: string) =>
    [...q.matchAll(new RegExp(key + ':"([^"]+)"', "g"))].map((m) => m[1] ?? "");
  return {
    text: q.replace(/(?:sector|region|impact):"[^"]+"/g, "").trim(),
    sectors: values("sector"),
    regions: values("region"),
    impactAreas: values("impact"),
  };
}
export const formatSearch = (f: SearchFilters) =>
  [
    f.text,
    ...f.sectors.map((v) => `sector:"${v}"`),
    ...f.regions.map((v) => `region:"${v}"`),
    ...f.impactAreas.map((v) => `impact:"${v}"`),
  ]
    .filter(Boolean)
    .join(" ");
export const isEmpty = (f: SearchFilters) =>
  !f.text && !f.sectors.length && !f.regions.length && !f.impactAreas.length;
export function matchesFilters(s: StartupSummary, f: SearchFilters) {
  const text = `${s.name} ${s.tagline} ${s.country} ${s.sector} ${s.region}`.toLowerCase();
  return (
    f.text
      .toLowerCase()
      .split(/\s+/)
      .every((t) => text.includes(t)) &&
    (!f.sectors.length || f.sectors.includes(s.sector)) &&
    (!f.regions.length || f.regions.includes(s.region)) &&
    (!f.impactAreas.length || f.impactAreas.some((a) => s.scores.ocean_areas_covered.includes(a)))
  );
}
