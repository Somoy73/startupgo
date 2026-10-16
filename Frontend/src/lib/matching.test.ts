import { describe, expect, it } from "vitest";
import { makeStartup } from "./fixtures";
import { matchBand, matchStartup, rankMatches, type Thesis } from "./matching";

const open: Thesis = {
  id: "t",
  name: "Test",
  stages: [],
  sectors: [],
  regions: [],
  impactAreas: [],
  minTrl: null,
  minBrl: null,
  minOceanImpact: null,
  qualityWeight: 0,
};

describe("matchStartup", () => {
  it("treats an open thesis as a full fit", () => {
    const m = matchStartup(makeStartup({ slug: "a" }), open);
    expect(m.criteria).toEqual([]);
    expect(m.fit).toBe(100);
  });

  it("scores each specified criterion", () => {
    const thesis: Thesis = { ...open, stages: ["series-a"], regions: ["europe"], impactAreas: ["C", "D"], minTrl: 7 };
    const m = matchStartup(makeStartup({ slug: "a", stage: "seed", country: "Portugal" }), thesis);
    const byKey = Object.fromEntries(m.criteria.map((c) => [c.key, c]));
    expect(byKey.stage).toMatchObject({ met: false, fit: 0 });
    expect(byKey.region).toMatchObject({ met: true, fit: 1, label: "Europe" });
    expect(byKey.impact).toMatchObject({ met: true, fit: 0.5 });
    expect(byKey.trl.fit).toBeCloseTo(1 / 3); // 2 levels short of 7
    expect(m.fit).toBe(Math.round((100 * (0 + 1 + 0.5 + 1 / 3)) / 4));
  });

  it("blends fit with investment potential by quality weight", () => {
    const s = makeStartup({ slug: "a", scores: { potential: 40 } });
    expect(matchStartup(s, { ...open, qualityWeight: 0.5 }).score).toBe(70);
  });
});

describe("rankMatches", () => {
  it("orders by match score, then potential", () => {
    const thesis = { ...open, regions: ["africa" as const] };
    const ranked = rankMatches(
      [
        makeStartup({ slug: "pt", country: "Portugal" }),
        makeStartup({ slug: "na-low", country: "Namibia", scores: { potential: 30 } }),
        makeStartup({ slug: "na-high", country: "Namibia", scores: { potential: 80 } }),
      ],
      thesis,
    );
    expect(ranked.map((m) => m.startup.slug)).toEqual(["na-high", "na-low", "pt"]);
  });
});

describe("matchBand", () => {
  it("requires every criterion met for a strong fit", () => {
    const strong = matchStartup(makeStartup({ slug: "a", scores: { potential: 90 } }), {
      ...open,
      minTrl: 5,
      qualityWeight: 0.3,
    });
    expect(matchBand(strong)).toBe("Strong fit");
    const partial = matchStartup(makeStartup({ slug: "b" }), { ...open, minTrl: 6, regions: ["europe"] });
    expect(matchBand(partial)).toBe("Partial fit");
  });
});
