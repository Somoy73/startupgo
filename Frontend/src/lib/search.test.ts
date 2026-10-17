import { describe, expect, it } from "vitest";
import { makeStartup } from "./fixtures";
import { emptyFilters, filterChips, formatSearch, matchesFilters, parseSearch, type Vocabulary } from "./search";

const vocab: Vocabulary = {
  sectors: ["Aquaculture", "Habitat restoration", "Materials & packaging"],
  countries: ["Namibia", "Portugal", "United Kingdom"],
};

describe("parseSearch", () => {
  it("extracts stage, region, level constraints and free text", () => {
    const f = parseSearch("Seed kelp startups in Europe with TRL >= 6", vocab);
    expect(f.stages).toEqual(["seed"]);
    expect(f.regions).toEqual(["europe"]);
    expect(f.minLevels).toEqual({ trl: 6 });
    expect(f.text).toEqual(["kelp"]);
  });

  it("prefers pre-seed over seed and handles level shorthands", () => {
    const f = parseSearch("pre-seed brl 5+ trl>7", vocab);
    expect(f.stages).toEqual(["pre-seed"]);
    expect(f.minLevels).toEqual({ brl: 5, trl: 8 });
  });

  it("recognises multi-word sectors, countries and aliases", () => {
    const f = parseSearch("habitat restoration uk namibia", vocab);
    expect(f.sectors).toEqual(["Habitat restoration"]);
    expect(f.countries).toEqual(["Namibia", "United Kingdom"]);
    expect(f.text).toEqual([]);
  });

  it("supports explicit key:value syntax with canonical casing", () => {
    const f = parseSearch('sector:"materials & packaging" area:b pipeline:diligence region:north-america', vocab);
    expect(f.sectors).toEqual(["Materials & packaging"]);
    expect(f.impactAreas).toEqual(["B"]);
    expect(f.pipeline).toEqual(["diligence"]);
    expect(f.regions).toEqual(["north-america"]);
  });

  it("returns empty filters for blank input", () => {
    expect(parseSearch("   ", vocab)).toEqual(emptyFilters());
  });
});

describe("formatSearch", () => {
  it("round-trips through parseSearch", () => {
    const f = parseSearch("series a aquaculture in united kingdom clean ocean screening tmrl>=6 offshore", vocab);
    expect(parseSearch(formatSearch(f), vocab)).toEqual(f);
  });
});

describe("matchesFilters", () => {
  const kelp = makeStartup({ slug: "kelp", tagline: "Giant kelp forests", country: "Namibia" });
  const bot = makeStartup({
    slug: "bot",
    tagline: "Cleanup robots",
    country: "Hong Kong",
    readiness: { trl: 7 },
    scores: { ocean_areas_covered: ["B"] },
  });

  it("ANDs facets and ORs values within a facet", () => {
    const f = parseSearch("region:africa region:asia", vocab);
    expect([kelp, bot].filter((s) => matchesFilters(s, f)).map((s) => s.slug)).toEqual(["kelp", "bot"]);
    const g = parseSearch("region:asia trl>=7 area:b", vocab);
    expect([kelp, bot].filter((s) => matchesFilters(s, g)).map((s) => s.slug)).toEqual(["bot"]);
  });

  it("matches free text against name, tagline, description, sector and location", () => {
    expect(matchesFilters(kelp, parseSearch("giant kelp", vocab))).toBe(true);
    expect(matchesFilters(kelp, parseSearch("robots", vocab))).toBe(false);
    const withDescription = { ...kelp, description: "Restores seagrass meadows" };
    expect(matchesFilters(withDescription, parseSearch("seagrass", vocab))).toBe(true);
  });
});

describe("filterChips", () => {
  it("removes exactly one value per chip", () => {
    const f = parseSearch("seed europe trl>=6 kelp", vocab);
    const chips = filterChips(f);
    expect(chips.map((c) => c.label)).toEqual(["Stage: Seed", "Region: Europe", "TRL ≥ 6", "“kelp”"]);
    expect(formatSearch(chips[2].without)).toBe("stage:seed region:europe kelp");
  });
});
