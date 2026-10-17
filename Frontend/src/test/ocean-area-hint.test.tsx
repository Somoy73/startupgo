import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AreaHint } from "@/components/OceanAreaChart";

const area = { code: "B", name: "A clean ocean" };
const kpi = { kpi_code: "B2", kpi_name: "Plastic avoided", area_code: "B", area_name: "A clean ocean", evidence_level: 2, evidence_label: "Evidenced", claim: "", source_url: null };

describe("AreaHint", () => {
  it("names the area and lists its evidenced KPIs", () => {
    render(<AreaHint area={area} best={2} kpis={[kpi]} />);
    fireEvent.click(screen.getByRole("button", { name: "B: A clean ocean, Evidenced" }));
    expect(screen.getByText("B · A clean ocean")).toBeInTheDocument();
    expect(screen.getByText("Strongest evidence: Evidenced")).toBeInTheDocument();
    expect(screen.getByText("Plastic avoided")).toBeInTheDocument();
  });

  it("says when an area has no evidence", () => {
    render(<AreaHint area={area} best={0} kpis={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "B: A clean ocean, None" }));
    expect(screen.getByText("No evidence recorded for this area.")).toBeInTheDocument();
  });
});
