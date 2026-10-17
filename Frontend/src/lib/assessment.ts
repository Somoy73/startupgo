import {
  DIMENSIONS,
  type Levels,
  type Confidence,
  type StartupDetail,
  type KPI,
} from "../api/types";
export type CompanyDraft = {
  name: string;
  tagline: string;
  sector: string;
  country: string;
  stage: string;
  roundDate: string;
  website: string;
  description: string;
};
export type AssessmentDraft = {
  levels: Levels;
  kpis: Record<string, KPI>;
  assessor: string;
  confidence: Confidence;
  rationale: string;
};
export type DraftErrors = Record<string, string>;
export const emptyCompany: CompanyDraft = {
  name: "",
  tagline: "",
  sector: "",
  country: "",
  stage: "seed",
  roundDate: "",
  website: "",
  description: "",
};
export const emptyAssessment = (): AssessmentDraft => ({
  levels: { trl: 1, brl: 1, crl: 1, frl: 1, ipr: 1, team: 1 },
  kpis: {},
  assessor: "",
  confidence: "low",
  rationale: "",
});
export const assessmentFromStartup = (s: StartupDetail): AssessmentDraft => ({
  levels: { ...s.levels },
  kpis: Object.fromEntries(s.ocean_kpis.map((k) => [k.code, k])),
  assessor: s.readiness.assessor,
  confidence: s.readiness.confidence,
  rationale: s.readiness.rationale,
});
export const validateCompany = (c: CompanyDraft): DraftErrors =>
  Object.fromEntries(
    ["name", "sector", "country"]
      .filter((k) => !c[k as keyof CompanyDraft].trim())
      .map((k) => [k, "Required"]),
  );
export const validateAssessment = (d: AssessmentDraft): DraftErrors =>
  d.assessor.trim() ? {} : { assessor: "Required" };
export const toAssessmentInput = (d: AssessmentDraft) => d;
export const toStartupInput = (company: CompanyDraft, draft: AssessmentDraft) => ({
  company,
  draft,
});
export const toPreviewInput = (
  draft: AssessmentDraft,
  stage: string,
  roundDate: string | null,
) => ({ draft, stage, roundDate });
export function previewScores(draft: AssessmentDraft) {
  const values = DIMENSIONS.map((d) => draft.levels[d.key]);
  const readiness = ((values.reduce((a, b) => a + b, 0) / 6 - 1) / 8) * 100;
  const spread = Math.max(...values) - Math.min(...values);
  const kpis = Object.values(draft.kpis).filter((k) => k.level > 0);
  const ocean = kpis.length ? Math.max(...kpis.map((k) => k.level)) * 25 : 0;
  const penalty = 3 * Math.max(0, spread - 3);
  const potential = Math.max(0, Math.round(0.45 * readiness + 0.35 * ocean + 0.2 * 50 - penalty));
  return {
    potential,
    readiness: Math.round(readiness),
    ocean_impact: ocean,
    momentum: 50,
    band:
      potential >= 70
        ? "Strong"
        : potential >= 55
          ? "Promising"
          : potential >= 40
            ? "Watch"
            : "Early",
    imbalance_penalty: penalty,
    readiness_spread: spread,
    lagging_dimensions: DIMENSIONS.filter((d) => draft.levels[d.key] === Math.min(...values)).map(
      (d) => d.key,
    ),
    ocean_areas_covered: [...new Set(kpis.map((k) => k.code.replace(/\d/g, "")))],
    ocean_evidence_label:
      ["None", "Intent", "Modelled", "Measured", "Verified"][
        kpis.length ? Math.max(...kpis.map((k) => k.level)) : 0
      ] ?? "None",
  };
}
