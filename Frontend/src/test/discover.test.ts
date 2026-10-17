import { describe, expect, it } from "vitest";
import { api } from "../api/client";
import { seed } from "../api/mock-data";
import { emptyFilters, filterChips, formatSearch, matchesFilters, parseSearch } from "../lib/search";
import { formatSort, nextSort, parseSort, sortStartups } from "../lib/sort";

const slugs = (list: { slug: string }[]) => list.map((s) => s.slug);
const matching = (encoded: string) => slugs(seed.filter((s) => matchesFilters(s, parseSearch(encoded))));

describe("Discover search (mock of POST /api/startups/search)", () => {
  it("returns the best match first, with relevance relative to it", async () => {
    const { results, entries } = await api.searchStartups("seaweed forests in Portugal");
    expect(results[0]?.slug).toBe("seaforester");
    expect(results[0]?.relevance).toBe(1);
    expect(results.every((r) => r.relevance > 0 && r.relevance <= 1)).toBe(true);
    expect(entries).toEqual([]);
  });

  it("ignores filler words and finds nothing for unrelated text", async () => {
    expect((await api.searchStartups("startups and companies")).results).toEqual([]);
    expect((await api.searchStartups("zorblax")).results).toEqual([]);
  });
});

describe("filters", () => {
  it("ANDs facets and ORs values within a facet", () => {
    expect(matching("region:Asia")).toEqual(["clearbot"]);
    expect(matching("region:Europe trl>=8")).toEqual(["sulapac"]);
    expect(matching("pipeline:diligence region:Asia region:Europe").sort()).toEqual(
      slugs(seed.filter((s) => s.pipeline_stage === "diligence")).sort(),
    );
  });

  it("matches sectors, countries and regions case-insensitively", () => {
    expect(matching("country:finland")).toEqual(matching("country:Finland"));
    expect(matching("region:asia")).toEqual(["clearbot"]);
  });

  it("round-trips through the URL encoding", () => {
    const f = {
      ...emptyFilters(),
      stages: ["seed"],
      sectors: ["Clean ocean"],
      regions: ["Europe"],
      pipeline: ["sourced" as const],
      minLevels: { trl: 6, ipr: 3 },
      anyText: ["kelp", "seaweed farm"],
      text: ["boats"],
    };
    expect(formatSearch(f)).toBe(
      'stage:seed sector:"Clean ocean" region:Europe pipeline:sourced trl>=6 iprl>=3 any:kelp any:"seaweed farm" boats',
    );
    expect(parseSearch(formatSearch(f))).toEqual(f);
  });

  it("gives one removable chip per value", () => {
    const chips = filterChips(parseSearch("region:Europe trl>=6 any:kelp"));
    expect(chips.map((c) => c.label)).toEqual(["Region: Europe", "TRL ≥ 6", "Any: “kelp”"]);
    expect(formatSearch(chips[1]!.without)).toBe("region:Europe any:kelp");
  });
});

describe("sorting", () => {
  it("defaults to relevance while searching and potential while browsing", () => {
    expect(parseSort(null, true)).toEqual({ key: "relevance", dir: "desc" });
    expect(parseSort(null, false)).toEqual({ key: "potential", dir: "desc" });
    expect(parseSort("relevance", false)).toEqual({ key: "potential", dir: "desc" });
  });

  it("reads and writes direction in the URL", () => {
    expect(parseSort("-trl", false)).toEqual({ key: "trl", dir: "desc" });
    expect(formatSort({ key: "name", dir: "asc" })).toBe("name");
  });

  it("cycles a header: natural direction, reversed, then the default order", () => {
    const first = nextSort({ key: "relevance", dir: "desc" }, "trl", true);
    const second = nextSort(first, "trl", true);
    expect([first, second, nextSort(second, "trl", true)]).toEqual([
      { key: "trl", dir: "desc" },
      { key: "trl", dir: "asc" },
      { key: "relevance", dir: "desc" },
    ]);
  });

  it("keeps the given order for relevance and sorts scores high to low", () => {
    const reversed = [...seed].reverse();
    expect(slugs(sortStartups(reversed, { key: "relevance", dir: "desc" }))).toEqual(slugs(reversed));
    const potentials = sortStartups(seed, { key: "potential", dir: "desc" }).map((s) => s.scores.potential);
    expect(potentials).toEqual([...potentials].sort((a, b) => b - a));
  });
});
