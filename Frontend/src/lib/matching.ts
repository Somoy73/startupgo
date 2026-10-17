/**
 * Thesis matching: how well does a startup fit an investor's thesis?
 *
 * Each criterion the thesis specifies yields a fit in [0, 1]. Criteria the thesis
 * leaves open are skipped. The match score blends average fit with the startup's
 * Investment Potential, weighted by `qualityWeight`.
 */
import type { StartupSummary } from "@/api/types";
import { stageLabel } from "./format";
import { inRegion, regionLabel, regionOf, type Region } from "./regions";

export interface Thesis {
  id: string;
  name: string;
  stages: string[];
  sectors: string[];
  regions: Region[];
  impactAreas: string[];
  minTrl: number | null;
  minBrl: number | null;
  minOceanImpact: number | null;
  /** Share of the match score that comes from Investment Potential (0-1). */
  qualityWeight: number;
}

export interface CriterionResult {
  key: string;
  met: boolean;
  fit: number;
  label: string;
}

export interface Match {
  startup: StartupSummary;
  criteria: CriterionResult[];
  /** Average criterion fit, 0-100. */
  fit: number;
  /** Blended fit and quality, 0-100. */
  score: number;
}

export type MatchBand = "Strong fit" | "Partial fit" | "Weak fit";

/** Levels below a minimum lose a third of the fit per missing level. */
const LEVEL_GAP_TOLERANCE = 3;

function oneOf(key: string, wanted: string[], actual: string | null, label: (v: string) => string): CriterionResult {
  const met = actual !== null && wanted.includes(actual);
  const shown = actual === null ? "Unknown" : label(actual);
  return {
    key,
    met,
    fit: met ? 1 : 0,
    label: met ? shown : `${shown} (thesis: ${wanted.map(label).join(", ")})`,
  };
}

function atLeast(key: string, name: string, min: number, actual: number): CriterionResult {
  const met = actual >= min;
  return {
    key,
    met,
    fit: met ? 1 : Math.max(0, 1 - (min - actual) / LEVEL_GAP_TOLERANCE),
    label: `${name} ${actual} ${met ? "≥" : "<"} ${min}`,
  };
}

export function evaluateCriteria(s: StartupSummary, t: Thesis): CriterionResult[] {
  const results: CriterionResult[] = [];

  if (t.stages.length) results.push(oneOf("stage", t.stages, s.stage, stageLabel));
  if (t.sectors.length) results.push(oneOf("sector", t.sectors, s.sector, (v) => v));
  if (t.regions.length) {
    const matched = t.regions.find((r) => inRegion(s.country, r));
    const continent = regionOf(s.country);
    results.push({
      key: "region",
      met: matched !== undefined,
      fit: matched !== undefined ? 1 : 0,
      label: matched
        ? regionLabel(matched)
        : `${continent ? regionLabel(continent) : "Unknown"} (thesis: ${t.regions.map(regionLabel).join(", ")})`,
    });
  }

  if (t.impactAreas.length) {
    const covered = t.impactAreas.filter((a) => s.scores.ocean_areas_covered.includes(a));
    results.push({
      key: "impact",
      met: covered.length > 0,
      fit: covered.length / t.impactAreas.length,
      label: covered.length
        ? `Impact ${covered.join(", ")} of ${t.impactAreas.join(", ")}`
        : `No impact in ${t.impactAreas.join(", ")}`,
    });
  }

  if (t.minTrl !== null) results.push(atLeast("trl", "TRL", t.minTrl, s.readiness.trl));
  if (t.minBrl !== null) results.push(atLeast("brl", "BRL", t.minBrl, s.readiness.brl));

  if (t.minOceanImpact !== null) {
    const actual = Math.round(s.scores.ocean_impact);
    const met = actual >= t.minOceanImpact;
    results.push({
      key: "ocean",
      met,
      fit: met ? 1 : t.minOceanImpact > 0 ? actual / t.minOceanImpact : 0,
      label: `Ocean impact ${actual} ${met ? "≥" : "<"} ${t.minOceanImpact}`,
    });
  }

  return results;
}

export function matchStartup(startup: StartupSummary, thesis: Thesis): Match {
  const criteria = evaluateCriteria(startup, thesis);
  const fit = criteria.length ? (100 * criteria.reduce((sum, c) => sum + c.fit, 0)) / criteria.length : 100;
  const w = Math.min(1, Math.max(0, thesis.qualityWeight));
  const score = (1 - w) * fit + w * startup.scores.potential;
  return { startup, criteria, fit: Math.round(fit), score: Math.round(score) };
}

export function rankMatches(startups: StartupSummary[], thesis: Thesis): Match[] {
  return startups
    .map((s) => matchStartup(s, thesis))
    .sort((a, b) => b.score - a.score || b.startup.scores.potential - a.startup.scores.potential);
}

export function matchBand(m: Match): MatchBand {
  const allMet = m.criteria.every((c) => c.met);
  if (allMet && m.score >= 70) return "Strong fit";
  if (m.fit >= 50) return "Partial fit";
  return "Weak fit";
}
