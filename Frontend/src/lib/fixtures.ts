import type { Readiness, Scores, StartupSummary } from "@/api/types";

type Overrides = Omit<Partial<StartupSummary>, "readiness" | "scores"> & {
  slug: string;
  readiness?: Partial<Readiness>;
  scores?: Partial<Scores>;
};

/** Builds a StartupSummary for unit tests; override only the fields a test cares about. */
export function makeStartup(overrides: Overrides): StartupSummary {
  return {
    name: overrides.slug,
    tagline: "",
    description: "",
    sector: "Aquaculture",
    country: "Portugal",
    city: null,
    stage: "seed",
    pipeline_stage: "sourced",
    total_disclosed_usd: null,
    last_round_on: null,
    ...overrides,
    readiness: {
      assessed_on: "2026-10-16",
      assessor: "test",
      confidence: "low",
      rationale: null,
      crl: 5,
      trl: 5,
      brl: 5,
      iprl: 5,
      tmrl: 5,
      frl: 5,
      ...overrides.readiness,
    },
    scores: {
      readiness: 50,
      ocean_impact: 50,
      momentum: 50,
      imbalance_penalty: 0,
      potential: 50,
      band: "Watch",
      readiness_spread: 0,
      lagging_dimensions: [],
      ocean_evidence_label: "Evidenced",
      ocean_areas_covered: ["C"],
      ...overrides.scores,
    },
  };
}
