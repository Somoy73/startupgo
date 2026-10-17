import { describe, expect, it } from "vitest";
import { api } from "../api/client";
import { seed } from "../api/mock-data";
import { emptyFilters, filterStartups, parseFilters, sortSearchResults } from "../lib/discover-search";

describe("Discover search", () => {
  it("returns the supplied search response with ranked matches and agent entries", async () => {
    const result = await api.searchStartups("find seaweed Finland startups");
    expect(result.query).toBe("find seaweed Finland startups");
    expect(result.results[0]?.slug).toBe("origin-by-ocean");
    expect(result.results[0]?.relevance).toBe(1);
    expect(result.results[0]?.matched).toEqual(["seaweed", "finland"]);
    expect(result.entries).toEqual([]);
  });
  it("does not invent matches for unknown queries", async () => {
    expect((await api.searchStartups("xyzunmatched")).results).toEqual([]);
  });
  it("combines region and sector filters", () => {
    expect(filterStartups(seed, { ...emptyFilters(), regions: ["Europe"], sectors: ["Seaweed"] }).map((s) => s.slug)).toEqual(["origin-by-ocean", "kelp-blue"]);
  });
  it("applies minimum readiness as an inclusive threshold", () => {
    expect(filterStartups(seed, { ...emptyFilters(), minLevels: { trl: 8 } }).map((s) => s.slug)).toEqual(["sulapac"]);
  });
  it("filters stage, pipeline and ocean impact together", () => {
    expect(filterStartups(seed, { ...emptyFilters(), stages: ["seed"], pipeline: ["diligence"], impactAreas: ["POL"] }).map((s) => s.slug)).toEqual(["clearbot"]);
  });
  it("sorts scores in both directions without changing original data", () => {
    expect(sortSearchResults(seed, { key: "ocean", direction: "desc" })[0]?.slug).toBe("kelp-blue");
    expect(sortSearchResults(seed, { key: "ocean", direction: "asc" })[0]?.slug).toBe("sulapac");
    expect(seed[0]?.slug).toBe("origin-by-ocean");
  });
  it("safely restores filter links and ignores invalid readiness levels", () => {
    expect(parseFilters('{"minLevels":{"trl":10,"brl":6}}').minLevels).toEqual({ brl: 6 });
    expect(parseFilters("invalid")).toEqual(emptyFilters());
  });
});