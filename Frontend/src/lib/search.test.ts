import { describe, expect, it } from "vitest";
import type { ApiSearchFilters } from "../api/types";
import {
  emptyFilters,
  filterChips,
  formatSearch,
  fromApiFilters,
  parseSearch,
  toApiFilters,
  type Vocabulary,
} from "./search";

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
    const f = { ...emptyFilters(), sectors: ["Materials & packaging"], countries: ["United Kingdom"], stages: ["seed"] };
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

describe("wire format", () => {
  const api: ApiSearchFilters = {
    stages: ["seed", "seed"],
    sectors: ["Aquaculture"],
    countries: [],
    regions: ["nordics", "atlantis"],
    impact_areas: ["c", "Z"],
    pipeline: ["diligence", "bogus"],
    min_levels: { crl: 0, trl: 7, brl: 12, iprl: 0, tmrl: 0, frl: 0 },
    keywords: [" Kelp "],
    any_keywords: ["Seaweed", "algae", ""],
  };

  it("maps backend filters to UI filters, dropping unknown values", () => {
    expect(fromApiFilters(api)).toEqual({
      ...emptyFilters(),
      stages: ["seed"],
      sectors: ["Aquaculture"],
      regions: ["nordics"],
      impactAreas: ["C"],
      pipeline: ["diligence"],
      minLevels: { trl: 7 },
      text: ["kelp"],
      anyText: ["seaweed", "algae"],
    });
  });

  it("round-trips UI filters through the wire format", () => {
    const f = parseSearch("seed nordics area:b pipeline:diligence trl>=6 brl>=4 any:kelp buoys", vocab);
    const wire = toApiFilters(f);
    expect(wire.min_levels).toEqual({ crl: 0, trl: 6, brl: 4, iprl: 0, tmrl: 0, frl: 0 });
    expect(fromApiFilters(wire)).toEqual(f);
  });
});
