import { describe, expect, it } from "vitest";
import type { StartupSummary } from "../api/backend-types";
import { emptyFilters, filterStartups, parseFilters, sortSearchResults } from "../lib/discover-search";

/** A backend StartupSummary (Backend/app/schemas.py) with the fields the tests vary. */
function startup(slug: string, o: { stage?: string; country?: string; sector?: string; pipeline?: StartupSummary["pipeline_stage"]; trl?: number; ocean?: number; areas?: string[]; funding?: number | null } = {}): StartupSummary {
  return {
    slug, name: slug, tagline: "", description: "", sector: o.sector ?? "Seaweed", country: o.country ?? "Denmark", city: null,
    stage: o.stage ?? "seed", pipeline_stage: o.pipeline ?? "sourced",
    readiness: { assessed_on: "2026-10-16", assessor: "test", confidence: "low", crl: 4, trl: o.trl ?? 4, brl: 4, iprl: 4, tmrl: 4, frl: 4, rationale: null },
    scores: { readiness: 50, ocean_impact: o.ocean ?? 50, momentum: 50, imbalance_penalty: 0, potential: 50, band: "Watch", readiness_spread: 0, lagging_dimensions: [], ocean_evidence_label: "", ocean_areas_covered: o.areas ?? [] },
    total_disclosed_usd: o.funding === undefined ? 1e6 : o.funding, last_round_on: null,
  };
}
const startups = [
  startup("notpla", { country: "United Kingdom", sector: "Packaging", pipeline: "diligence", trl: 8, ocean: 70, areas: ["B", "D"] }),
  startup("kelp-blue", { country: "Namibia", stage: "series-a", ocean: 90, areas: ["A", "C"] }),
  startup("clearbot", { country: "Hong Kong", sector: "Ocean cleanup", ocean: 20, areas: ["B"], funding: null }),
];
const slugs = (items: StartupSummary[]) => items.map((s) => s.slug);

describe("Discover search", () => {
  it("combines country and sector filters", () => {
    expect(slugs(filterStartups(startups, { ...emptyFilters(), countries: ["Namibia", "Hong Kong"], sectors: ["Seaweed"] }))).toEqual(["kelp-blue"]);
  });
  it("applies minimum readiness as an inclusive threshold", () => {
    expect(slugs(filterStartups(startups, { ...emptyFilters(), minLevels: { trl: 8 } }))).toEqual(["notpla"]);
  });
  it("filters stage, pipeline and ocean impact together", () => {
    expect(slugs(filterStartups(startups, { ...emptyFilters(), stages: ["seed"], pipeline: ["diligence"], impactAreas: ["B"] }))).toEqual(["notpla"]);
  });
  it("sorts scores in both directions without changing original data", () => {
    expect(sortSearchResults(startups, { key: "ocean", direction: "desc" })[0]?.slug).toBe("kelp-blue");
    expect(sortSearchResults(startups, { key: "ocean", direction: "asc" })[0]?.slug).toBe("clearbot");
    expect(startups[0]?.slug).toBe("notpla");
  });
  it("sorts undisclosed funding as zero", () => {
    expect(sortSearchResults(startups, { key: "funding", direction: "asc" })[0]?.slug).toBe("clearbot");
  });
  it("sorts by relevance when results carry it", () => {
    const matches = startups.map((s, i) => ({ ...s, relevance: [0.2, 0.5, 1][i] ?? 0, matched: [], entry: null }));
    expect(slugs(sortSearchResults(matches, { key: "relevance", direction: "desc" }))).toEqual(["clearbot", "kelp-blue", "notpla"]);
  });
  it("safely restores filter links and ignores invalid readiness levels and pipeline stages", () => {
    expect(parseFilters('{"minLevels":{"trl":10,"brl":6}}').minLevels).toEqual({ brl: 6 });
    expect(parseFilters('{"pipeline":["portfolio","invested"]}').pipeline).toEqual(["portfolio"]);
    expect(parseFilters("invalid")).toEqual(emptyFilters());
  });
});
