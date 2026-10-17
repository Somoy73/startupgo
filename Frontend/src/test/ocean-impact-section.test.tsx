import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OceanImpactSection } from "@/components/OceanImpactSection";

const kpi = { kpi_code: "B2", kpi_name: "Plastic avoided", area_code: "B", area_name: "A clean ocean", evidence_level: 2, evidence_label: "Evidenced", claim: "Replaces 1M plastic sachets a year.", source_url: null };

describe("OceanImpactSection", () => {
  it("keeps the KPI claims behind Show details", () => {
    render(<OceanImpactSection kpis={[kpi]} areas={null} />);
    expect(screen.getByText("Replaces 1M plastic sachets a year.")).not.toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Show details" }));
    expect(screen.getByText("Replaces 1M plastic sachets a year.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Hide details" })).toHaveAttribute("aria-expanded", "true");
  });

  it("has no toggle without evidence", () => {
    render(<OceanImpactSection kpis={[{ ...kpi, evidence_level: 0 }]} areas={null} />);
    expect(screen.getByText("No impact evidence recorded.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show details" })).not.toBeInTheDocument();
  });
});
