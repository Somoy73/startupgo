import { describe, expect, it } from "vitest";
import {
  emptyAssessment,
  emptyCompany,
  toAssessmentInput,
  toPreviewInput,
  toStartupInput,
  validateAssessment,
  validateCompany,
} from "./assessment";

describe("validateAssessment", () => {
  it("requires an assessor and a claim for every KPI with evidence", () => {
    const draft = { ...emptyAssessment(), kpis: { B2: { level: 2, claim: "", sourceUrl: "" } } };
    expect(validateAssessment(draft)).toEqual({
      assessor: expect.any(String),
      "kpi.B2": expect.stringContaining("claim"),
    });
  });

  it("ignores KPIs set back to zero and rejects non-http sources", () => {
    const draft = {
      ...emptyAssessment(),
      assessor: "Ana",
      kpis: {
        A1: { level: 0, claim: "", sourceUrl: "" },
        D1: { level: 1, claim: "Cuts fuel", sourceUrl: "ftp://x" },
      },
    };
    expect(Object.keys(validateAssessment(draft))).toEqual(["kpi.D1"]);
  });
});

describe("validateCompany", () => {
  it("flags missing required fields and malformed optional ones", () => {
    const errors = validateCompany({ ...emptyCompany(), foundedYear: "21", roundAmount: "abc", roundDate: "May 2026" });
    expect(Object.keys(errors).sort()).toEqual(
      [
        "company.country",
        "company.description",
        "company.foundedYear",
        "company.name",
        "company.roundAmount",
        "company.roundDate",
        "company.sector",
        "company.tagline",
      ].sort(),
    );
  });
});

describe("conversion", () => {
  const draft = {
    ...emptyAssessment(),
    assessor: " Ana ",
    kpis: {
      A1: { level: 0, claim: "dropped", sourceUrl: "" },
      C5: { level: 2, claim: " Restores kelp ", sourceUrl: "" },
    },
  };

  it("sends only KPIs with evidence, trimmed", () => {
    expect(toAssessmentInput(draft).ocean_kpis).toEqual([
      { kpi_code: "C5", evidence_level: 2, claim: "Restores kelp", source_url: null },
    ]);
    expect(toAssessmentInput(draft).assessor).toBe("Ana");
  });

  it("only includes a funding round when one was entered", () => {
    const base = { ...emptyCompany(), name: "X", tagline: "t", description: "d", sector: "s", country: "c" };
    expect(toStartupInput(base, draft).funding_round).toBeNull();
    const withRound = toStartupInput({ ...base, roundAmount: "500000", roundDate: "2026-06" }, draft);
    expect(withRound.funding_round).toMatchObject({ round_type: "seed", amount: 500000, currency: "EUR" });
  });

  it("drops an invalid last-round date from score previews", () => {
    expect(toPreviewInput(draft, "seed", "June").last_round_on).toBeNull();
    expect(toPreviewInput(draft, "seed", "2026-06").last_round_on).toBe("2026-06");
  });
});
