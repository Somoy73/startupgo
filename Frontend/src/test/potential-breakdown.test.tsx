import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Scores } from "@/api/backend-types";
import { PotentialBreakdown } from "@/components/PotentialBreakdown";

const weights = { readiness: 0.45, ocean_impact: 0.3, momentum: 0.25 };
const scores = (o: Partial<Scores>): Scores => ({
  readiness: 60, ocean_impact: 50, momentum: 40, imbalance_penalty: 0, potential: 52,
  band: "Watch", readiness_spread: 2, lagging_dimensions: [], ocean_evidence_label: "", ocean_areas_covered: [], ...o,
});

describe("PotentialBreakdown", () => {
  it("shows each score times its weight", () => {
    render(<PotentialBreakdown scores={scores({})} weights={weights} />);
    expect(screen.getByText("60 × 0.45 =")).toBeInTheDocument();
    expect(screen.getByText("27.0")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName("Investment potential 52: Readiness 27.0, Ocean impact 15.0, Momentum 10.0");
    expect(screen.queryByText("Imbalance penalty")).not.toBeInTheDocument();
  });

  it("takes the imbalance penalty off the end of the stack", () => {
    // Kelp Blue: 0.45 × 40 + 0.30 × 50 + 0.25 × 40 = 43, minus 5.
    render(<PotentialBreakdown scores={scores({ readiness: 40, momentum: 40, imbalance_penalty: 5, potential: 38, readiness_spread: 4 })} weights={weights} />);
    expect(screen.getByText("−5.0")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName(/minus imbalance penalty 5\.0$/);
    const bar = screen.getByRole("img");
    const struck = bar.querySelectorAll(".penalty-stripes");
    expect([...struck].reduce((sum, el) => sum + parseFloat((el as HTMLElement).style.width), 0)).toBeCloseTo(5);
  });
});
