import { describe, expect, it } from "vitest";
import { makeStartup } from "./fixtures";
import { formatSort, nextSort, parseSort, sortStartups, type Sort } from "./sort";

const ranked = [
  makeStartup({ slug: "best-match", name: "Zeta", scores: { potential: 40 }, total_disclosed_usd: null }),
  makeStartup({ slug: "second", name: "Alpha", scores: { potential: 90 }, total_disclosed_usd: 5_000_000 }),
  makeStartup({ slug: "third", name: "Mid", scores: { potential: 60 }, total_disclosed_usd: 1_000_000 }),
];
const order = (sort: Sort) => sortStartups(ranked, sort).map((s) => s.slug);

describe("sortStartups", () => {
  it("keeps the search's order for relevance", () => {
    expect(order({ key: "relevance", dir: "desc" })).toEqual(["best-match", "second", "third"]);
  });

  it("sorts by a score or by name in either direction", () => {
    expect(order({ key: "potential", dir: "desc" })).toEqual(["second", "third", "best-match"]);
    expect(order({ key: "potential", dir: "asc" })).toEqual(["best-match", "third", "second"]);
    expect(order({ key: "name", dir: "asc" })).toEqual(["second", "third", "best-match"]);
  });

  it("puts missing values last in both directions", () => {
    expect(order({ key: "funding", dir: "desc" })).toEqual(["second", "third", "best-match"]);
    expect(order({ key: "funding", dir: "asc" })).toEqual(["third", "second", "best-match"]);
  });
});

describe("parseSort / formatSort", () => {
  it("defaults to relevance while searching and potential while browsing", () => {
    expect(parseSort(null, true)).toEqual({ key: "relevance", dir: "desc" });
    expect(parseSort(null, false)).toEqual({ key: "potential", dir: "desc" });
  });

  it("reads direction from a leading minus and round-trips", () => {
    expect(parseSort("-trl", false)).toEqual({ key: "trl", dir: "desc" });
    expect(parseSort("name", false)).toEqual({ key: "name", dir: "asc" });
    expect(formatSort({ key: "trl", dir: "desc" })).toBe("-trl");
    expect(formatSort({ key: "name", dir: "asc" })).toBe("name");
  });

  it("ignores unknown keys, and relevance when not searching", () => {
    expect(parseSort("-bogus", true)).toEqual({ key: "relevance", dir: "desc" });
    expect(parseSort("relevance", false)).toEqual({ key: "potential", dir: "desc" });
  });
});

describe("nextSort", () => {
  it("cycles natural direction → reversed → default", () => {
    const first = nextSort({ key: "relevance", dir: "desc" }, "trl", true);
    expect(first).toEqual({ key: "trl", dir: "desc" });
    const second = nextSort(first, "trl", true);
    expect(second).toEqual({ key: "trl", dir: "asc" });
    expect(nextSort(second, "trl", true)).toEqual({ key: "relevance", dir: "desc" });
  });

  it("starts names ascending", () => {
    expect(nextSort({ key: "potential", dir: "desc" }, "name", false)).toEqual({ key: "name", dir: "asc" });
  });
});
