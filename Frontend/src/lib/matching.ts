import type { StartupDetail } from "../api/types";
export type Thesis = {
  id: string;
  name: string;
  sectors: string[];
  impactAreas: string[];
  minTrl: number;
  minPotential: number;
  preset?: boolean;
};
export type Match = { startup: StartupDetail; fit: number; reasons: string[] };
export const rankMatches = (startups: StartupDetail[], thesis: Thesis): Match[] =>
  startups
    .map((startup) => {
      const reasons = [
        !thesis.sectors.length || thesis.sectors.includes(startup.sector) ? "Sector alignment" : "",
        startup.readiness.trl >= thesis.minTrl ? "Readiness threshold met" : "",
        startup.scores.potential >= thesis.minPotential ? "Investment potential threshold met" : "",
        !thesis.impactAreas.length ||
        thesis.impactAreas.some((a) => startup.scores.ocean_areas_covered.includes(a))
          ? "Impact alignment"
          : "",
      ].filter(Boolean);
      return { startup, fit: reasons.length * 25, reasons };
    })
    .sort((a, b) => b.fit - a.fit || b.startup.scores.potential - a.startup.scores.potential);
export const matchBand = (m: Match) =>
  m.fit >= 75 ? "Strong fit" : m.fit >= 50 ? "Partial fit" : "Weak fit";
