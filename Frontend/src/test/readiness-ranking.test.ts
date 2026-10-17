import { describe, expect, it } from "vitest";
import type { StartupSummary } from "../api/backend-types";
import { rankByReadiness } from "../lib/readiness-ranking";

const startup = (slug: string, readiness: number, assessed = true) =>
  ({ slug, name: slug, assessed, scores: { readiness, ocean_impact: 10, potential: 20 } }) as StartupSummary;

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
