import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Scores } from "@/api/backend-types";
import { PotentialBreakdown } from "@/components/PotentialBreakdown";

const weights = { readiness: 0.45, ocean_impact: 0.3, momentum: 0.25 };
const scores = (o: Partial<Scores>): Scores => ({
  readiness: 60, ocean_impact: 50, momentum: 40, potential: 52,
  band: "Watch", readiness_spread: 2, lagging_dimensions: [], ocean_evidence_label: "", ocean_areas_covered: [], ...o,
});

describe("PotentialBreakdown", () => {
  it("shows each score times its weight", () => {
    render(<PotentialBreakdown scores={scores({})} weights={weights} />);
    expect(screen.getByText("60 × 0.45 =")).toBeInTheDocument();
    expect(screen.getByText("27.0")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName("Investment potential 52: Readiness 27.0, Ocean impact 15.0, Momentum 10.0");
  });

  it("fills the bar to the potential, one segment per score", () => {
    render(<PotentialBreakdown scores={scores({})} weights={weights} />);
    const widths = [...screen.getByRole("img").children].map((el) => parseFloat((el as HTMLElement).style.width));
    expect(widths).toEqual([27, 15, 10]);
  });
});
