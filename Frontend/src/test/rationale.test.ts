import { describe, expect, it } from "vitest";
import { rationalePoints } from "../lib/format";

describe("rationalePoints", () => {
  it("splits a seed estimate's note on semicolons", () => {
    expect(rationalePoints("Products on the market and a large Series A+ imply commercial traction; IP position not verified.")).toEqual([
      "Products on the market and a large Series A+ imply commercial traction.",
      "IP position not verified.",
    ]);
  });

  it("tidies the agent's status line", () => {
    expect(rationalePoints("no evidence for CRL, TRL (stored as 1); judge accepted_with_issues with 6 open issue(s); agent entry hivelife-com")).toEqual([
      "No evidence for CRL, TRL (stored as 1).",
      "Judge accepted with issues with 6 open issue(s).",
      "Agent entry hivelife-com.",
    ]);
  });

  it("keeps a single sentence as one point and drops empty text", () => {
    expect(rationalePoints("Thousands of buoys deployed.")).toEqual(["Thousands of buoys deployed."]);
    expect(rationalePoints(null)).toEqual([]);
    expect(rationalePoints(" ; ")).toEqual([]);
  });
});
