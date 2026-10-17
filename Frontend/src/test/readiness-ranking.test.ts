import { describe, expect, it } from "vitest";
import type { StartupSummary } from "../api/backend-types";
import { rankByReadiness, similarStartups } from "../lib/readiness-ranking";

const startup = (slug: string, readiness: number, assessed = true, sector = "Seaweed") =>
  ({ slug, name: slug, sector, assessed, scores: { readiness, ocean_impact: 10, potential: 20 } }) as StartupSummary;

describe("rankByReadiness", () => {
  it("orders by readiness descending, ties by name, and skips unassessed startups", () => {
    const ranked = rankByReadiness([startup("b", 50), startup("a", 50), startup("c", 80), startup("x", 0, false)]);
    expect(ranked.map((r) => r.startup.slug)).toEqual(["c", "a", "b"]);
    expect(ranked[0]).toMatchObject({ total: 80, readiness: 80, impact: 10, potential: 20 });
  });

  it("keeps only the top n", () => {
    expect(rankByReadiness([startup("a", 1), startup("b", 2), startup("c", 3)], 2).map((r) => r.startup.slug)).toEqual(["c", "b"]);
  });
});

describe("similarStartups", () => {
  it("prefers the same sector, then the closest readiness, and leaves out the picked one", () => {
    const pool = rankByReadiness([
      startup("picked", 60),
      startup("near-other-sector", 61, true, "Shipping"),
      startup("far-same-sector", 20),
      startup("near-same-sector", 55),
      startup("mid-other-sector", 70, true, "Shipping"),
    ], Infinity);
    const picked = pool.find((r) => r.startup.slug === "picked")!;
    expect(similarStartups(picked, pool).map((r) => r.startup.slug)).toEqual(["near-same-sector", "far-same-sector", "near-other-sector"]);
  });
});
