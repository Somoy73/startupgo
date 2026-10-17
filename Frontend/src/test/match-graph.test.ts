import { describe, expect, it } from "vitest";
import { seed } from "../api/mock-data";
import { topInvestorMatches } from "../lib/investor";
import { layoutNodes } from "../lib/match-graph";

describe("investor match graph", () => {
  it("shows only the 5 closest matches, best first", () => {
    const m = topInvestorMatches(seed, 5);
    expect(m).toHaveLength(5);
    for (let i = 1; i < m.length; i++) expect(m[i - 1]!.total).toBeGreaterThanOrEqual(m[i]!.total);
  });
  it("puts higher scores closer to the center, inside the outer ring", () => {
    const size = 360;
    const nodes = layoutNodes([{ slug: "a", score: 90 }, { slug: "b", score: 40 }], size);
    const d = (n: (typeof nodes)[number]) => Math.hypot(n.x - size / 2, n.y - size / 2);
    expect(d(nodes[0]!)).toBeLessThan(d(nodes[1]!));
    nodes.forEach((n) => expect(d(n)).toBeLessThanOrEqual(size * 0.44 + 0.01));
  });
});
