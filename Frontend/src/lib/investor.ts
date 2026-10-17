import type { StartupDetail } from "../api/types";

/** Fixed investor interests (placeholder until real ones are provided). */
export const INVESTOR = {
  sectors: ["Seaweed", "Clean ocean", "Restoration"],
  impactAreas: ["BIO", "POL"],
  minTrl: 5,
};

export type InvestorMatch = {
  startup: StartupDetail;
  total: number;
  thesis: number;
  readiness: number;
  impact: number;
};

export function scoreForInvestor(s: StartupDetail): InvestorMatch {
  const sector = INVESTOR.sectors.includes(s.sector) ? 60 : 20;
  const area = s.scores.ocean_areas_covered.some((a) => INVESTOR.impactAreas.includes(a)) ? 25 : 0;
  const trl = s.readiness.trl >= INVESTOR.minTrl ? 15 : 0;
  const thesis = sector + area + trl;
  const readiness = Math.round(s.scores.readiness);
  const impact = Math.round(s.scores.ocean_impact);
  const total = Math.round(0.5 * thesis + 0.25 * readiness + 0.25 * impact);
  return { startup: s, total, thesis, readiness, impact };
}

export const topInvestorMatches = (startups: StartupDetail[], n = 5) =>
  startups
    .map(scoreForInvestor)
    .sort((a, b) => b.total - a.total || a.startup.name.localeCompare(b.startup.name))
    .slice(0, n);
