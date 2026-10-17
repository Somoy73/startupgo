/**
 * Assessment form model: editable drafts, conversion to API inputs, and validation.
 * Kept free of React so it can be unit tested.
 */
import {
  DIMENSIONS,
  type AssessmentInput,
  type Confidence,
  type FundingStage,
  type Levels,
  type ScorePreviewInput,
  type StartupDetail,
  type StartupInput,
} from "@/api/types";

export interface KpiDraft {
  level: number;
  claim: string;
  sourceUrl: string;
}

export interface AssessmentDraft {
  levels: Levels;
  kpis: Record<string, KpiDraft>;
  assessor: string;
  confidence: Confidence;
  rationale: string;
}

export interface CompanyDraft {
  name: string;
  tagline: string;
  description: string;
  sector: string;
  country: string;
  city: string;
  foundedYear: string;
  website: string;
  stage: FundingStage;
  roundAmount: string;
  roundCurrency: string;
  roundDate: string;
  roundLead: string;
}

/** Field path → message, e.g. "company.name" or "kpi.B2". */
export type DraftErrors = Record<string, string>;

const DEFAULT_LEVEL = 1;
const PARTIAL_DATE = /^\d{4}(-\d{2}(-\d{2})?)?$/;
const URL_PATTERN = /^https?:\/\/\S+$/i;

export const EMPTY_KPI: KpiDraft = { level: 0, claim: "", sourceUrl: "" };

export function emptyAssessment(): AssessmentDraft {
  return {
    levels: Object.fromEntries(DIMENSIONS.map((d) => [d.key, DEFAULT_LEVEL])) as Levels,
    kpis: {},
    assessor: "",
    confidence: "medium",
    rationale: "",
  };
}

export function emptyCompany(): CompanyDraft {
  return {
    name: "",
    tagline: "",
    description: "",
    sector: "",
    country: "",
    city: "",
    foundedYear: "",
    website: "",
    stage: "seed",
    roundAmount: "",
    roundCurrency: "EUR",
    roundDate: "",
    roundLead: "",
  };
}

/** Pre-fill a new assessment from the startup's current one. */
export function assessmentFromStartup(s: StartupDetail): AssessmentDraft {
  return {
    levels: Object.fromEntries(DIMENSIONS.map((d) => [d.key, s.readiness[d.key]])) as Levels,
    kpis: Object.fromEntries(
      s.ocean_kpis.map((k) => [k.kpi_code, { level: k.evidence_level, claim: k.claim, sourceUrl: k.source_url ?? "" }]),
    ),
    assessor: "",
    confidence: "medium",
    rationale: "",
  };
}

const activeKpis = (draft: AssessmentDraft) => Object.entries(draft.kpis).filter(([, k]) => k.level > 0);
const orNull = (v: string) => v.trim() || null;

export function toAssessmentInput(draft: AssessmentDraft): AssessmentInput {
  return {
    ...draft.levels,
    assessor: draft.assessor.trim(),
    confidence: draft.confidence,
    rationale: orNull(draft.rationale),
    ocean_kpis: activeKpis(draft).map(([code, k]) => ({
      kpi_code: code,
      evidence_level: k.level,
      claim: k.claim.trim(),
      source_url: orNull(k.sourceUrl),
    })),
  };
}

export function toStartupInput(company: CompanyDraft, draft: AssessmentDraft): StartupInput {
  const hasRound = Boolean(company.roundAmount.trim() || company.roundDate.trim() || company.roundLead.trim());
  return {
    name: company.name.trim(),
    tagline: company.tagline.trim(),
    description: company.description.trim(),
    sector: company.sector.trim(),
    country: company.country.trim(),
    city: orNull(company.city),
    founded_year: company.foundedYear.trim() ? Number(company.foundedYear) : null,
    website: orNull(company.website),
    stage: company.stage,
    funding_round: hasRound
      ? {
          round_type: company.stage,
          amount: company.roundAmount.trim() ? Number(company.roundAmount) : null,
          currency: company.roundAmount.trim() ? company.roundCurrency.trim().toUpperCase() : null,
          announced_on: orNull(company.roundDate),
          lead_investors: orNull(company.roundLead),
        }
      : null,
    assessment: toAssessmentInput(draft),
  };
}

export function toPreviewInput(draft: AssessmentDraft, stage: string, lastRoundOn: string | null): ScorePreviewInput {
  return {
    ...draft.levels,
    ocean_kpis: activeKpis(draft).map(([code, k]) => ({ kpi_code: code, evidence_level: k.level })),
    stage,
    last_round_on: lastRoundOn && PARTIAL_DATE.test(lastRoundOn) ? lastRoundOn : null,
  };
}

export function validateAssessment(draft: AssessmentDraft): DraftErrors {
  const errors: DraftErrors = {};
  if (!draft.assessor.trim()) errors.assessor = "Who is making this assessment?";
  for (const [code, k] of activeKpis(draft)) {
    if (!k.claim.trim()) errors[`kpi.${code}`] = "Describe the claim behind this evidence level.";
    else if (k.sourceUrl.trim() && !URL_PATTERN.test(k.sourceUrl.trim()))
      errors[`kpi.${code}`] = "Source must be an http(s) link.";
  }
  return errors;
}

export function validateCompany(c: CompanyDraft): DraftErrors {
  const errors: DraftErrors = {};
  const required: [keyof CompanyDraft, string][] = [
    ["name", "Name"],
    ["tagline", "Tagline"],
    ["description", "Description"],
    ["sector", "Sector"],
    ["country", "Country"],
  ];
  for (const [key, label] of required) if (!c[key].trim()) errors[`company.${key}`] = `${label} is required.`;

  const year = c.foundedYear.trim();
  if (year && !(/^\d{4}$/.test(year) && Number(year) >= 1900 && Number(year) <= 2100))
    errors["company.foundedYear"] = "Use a four-digit year.";
  if (c.website.trim() && !URL_PATTERN.test(c.website.trim())) errors["company.website"] = "Use a full http(s) link.";
  if (c.roundAmount.trim() && !(Number(c.roundAmount) >= 0)) errors["company.roundAmount"] = "Amount must be a number.";
  if (c.roundAmount.trim() && !/^[A-Za-z]{3}$/.test(c.roundCurrency.trim()))
    errors["company.roundCurrency"] = "Use a 3-letter currency code.";
  if (c.roundDate.trim() && !PARTIAL_DATE.test(c.roundDate.trim()))
    errors["company.roundDate"] = "Use YYYY, YYYY-MM or YYYY-MM-DD.";
  return errors;
}
