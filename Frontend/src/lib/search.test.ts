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

  it("recognises multi-word sectors, countries, aliases and sub-regions", () => {
    const f = parseSearch("habitat restoration uk namibia nordic", vocab);
    expect(f.sectors).toEqual(["Habitat restoration"]);
    expect(f.countries).toEqual(["Namibia", "United Kingdom"]);
    expect(f.regions).toEqual(["nordics"]);
    expect(f.text).toEqual([]);
  });

  it("supports explicit key:value syntax with canonical casing", () => {
    const f = parseSearch('sector:"materials & packaging" area:b pipeline:diligence region:baltics any:kelp', vocab);
    expect(f.sectors).toEqual(["Materials & packaging"]);
    expect(f.impactAreas).toEqual(["B"]);
    expect(f.pipeline).toEqual(["diligence"]);
    expect(f.regions).toEqual(["baltics"]);
    expect(f.anyText).toEqual(["kelp"]);
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

  it("round-trips any: terms with spaces", () => {
    const f = parseSearch('nordics any:"giant kelp" any:seaweed trl>=5', vocab);
    expect(f.anyText).toEqual(["giant kelp", "seaweed"]);
    expect(parseSearch(formatSearch(f), vocab)).toEqual(f);
  });

  it("decodes the URL form without the data vocabulary", () => {
    const f = {
      ...emptyFilters(),
      sectors: ["Materials & packaging"],
      countries: ["United Kingdom"],
      stages: ["seed"],
    };
    const decoded = parseSearch(formatSearch(f), { sectors: [], countries: [] });
    // Casing is restored by the backend, which matches sectors and countries case-insensitively.
    expect(decoded).toEqual({ ...f, sectors: ["materials & packaging"], countries: ["united kingdom"] });
  });
});

describe("filterChips", () => {
  it("removes exactly one value per chip", () => {
    const f = parseSearch("seed europe trl>=6 any:algae kelp", vocab);
    const chips = filterChips(f);
    expect(chips.map((c) => c.label)).toEqual(["Stage: Seed", "Region: Europe", "TRL ≥ 6", "Any: “algae”", "“kelp”"]);
    expect(formatSearch(chips[2].without)).toBe("stage:seed region:europe any:algae kelp");
  });
});

describe("matchesFilters", () => {
  const kelp = makeStartup({
    slug: "kelp",
    tagline: "Giant kelp forests",
    country: "Faroe Islands",
    sector: "Aquaculture",
  });
  const bot = makeStartup({
    slug: "bot",
    tagline: "Cleanup robots",
    country: "Hong Kong",
    sector: "Ocean cleanup",
    readiness: { trl: 7 },
    scores: { ocean_areas_covered: ["B"] },
  });
  const match = (q: string) => [kelp, bot].filter((s) => matchesFilters(s, parseSearch(q, vocab))).map((s) => s.slug);

  it("ANDs facets and ORs values within a facet", () => {
    expect(match("region:europe region:asia")).toEqual(["kelp", "bot"]);
    expect(match("region:asia trl>=7 area:b")).toEqual(["bot"]);
    expect(match("region:nordics")).toEqual(["kelp"]);
  });

  it("matches sectors and countries case-insensitively, as decoded from the URL", () => {
    expect(match('sector:aquaculture country:"faroe islands"')).toEqual(["kelp"]);
  });

  it("matches all text terms and at least one any: term", () => {
    expect(match("giant kelp")).toEqual(["kelp"]);
    expect(match("any:robots any:seagrass")).toEqual(["bot"]);
    expect(match("robots any:kelp")).toEqual([]);
  });

  it("lets everything through with no filters", () => {
    expect(match("")).toEqual(["kelp", "bot"]);
  });
});
