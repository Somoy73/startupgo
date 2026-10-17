import { describe, expect, it } from "vitest";
import { makeStartup } from "./fixtures";
import { effectiveSort, sortStartups } from "./sort";

const ranked = [
  makeStartup({ slug: "best-match", name: "Zeta", scores: { potential: 40 } }),
  makeStartup({ slug: "second", name: "Alpha", scores: { potential: 90 } }),
  makeStartup({ slug: "third", name: "Mid", scores: { potential: 60 } }),
];
const order = (key: Parameters<typeof sortStartups>[1]) => sortStartups(ranked, key).map((s) => s.slug);

describe("sortStartups", () => {
  it("keeps the search's order for relevance", () => {
    expect(order("relevance")).toEqual(["best-match", "second", "third"]);
  });

  it("re-sorts by a score or by name", () => {
    expect(order("potential")).toEqual(["second", "third", "best-match"]);
    expect(order("name")).toEqual(["second", "third", "best-match"]);
  });
});

describe("effectiveSort", () => {
  it("defaults to relevance while searching and potential while browsing", () => {
    expect(effectiveSort(null, true)).toBe("relevance");
    expect(effectiveSort(null, false)).toBe("potential");
  });

  it("honours an explicit choice, except relevance when not searching", () => {
    expect(effectiveSort("trl", true)).toBe("trl");
    expect(effectiveSort("trl", false)).toBe("trl");
    expect(effectiveSort("relevance", false)).toBe("potential");
    expect(effectiveSort("bogus", true)).toBe("relevance");
  });
});
