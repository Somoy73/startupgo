import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReadinessProfile } from "@/components/ReadinessProfile";

const levels = [
  { dimension: "CRL", name: "Customer", level: 8, summary: "Market-ready product sold near target price.", next_summary: "Widespread, repeatable, scalable sales." },
  { dimension: "TRL", name: "Technology", level: 9, summary: "Proven over time.", next_summary: null },
];

describe("ReadinessProfile", () => {
  it("keeps the general KTH definitions behind a hint", () => {
    render(<ReadinessProfile levels={levels} lagging={["TRL"]} />);
    expect(screen.queryByText(/Market-ready product/)).not.toBeInTheDocument();
    expect(screen.getByText("· lagging")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "What CRL 8 means" }));
    expect(screen.getByText("Market-ready product sold near target price.")).toBeInTheDocument();
    expect(screen.getByText("Widespread, repeatable, scalable sales.")).toBeInTheDocument();
  });

  it("has no next level at 9", () => {
    render(<ReadinessProfile levels={levels} lagging={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "What TRL 9 means" }));
    expect(screen.getByText("Proven over time.")).toBeInTheDocument();
    expect(screen.queryByText(/Next, TRL/)).not.toBeInTheDocument();
  });
});
