import type { FundingEvent } from "../api/backend-types";
import type { ChartPalette } from "./chart-theme";
import { stageLabel, toEur } from "./format";

/** Funding event types, grouped the way the timeline colours them and the table labels them. */
export const FUNDING_KINDS = {
  equity: { label: "Equity round", types: ["announced_round", "priced_round", "round"], color: "primary" },
  filing: { label: "SEC filing", types: ["form_d"], color: "navy" },
  grant: { label: "Grant", types: ["eu_grant", "grant"], color: "success" },
  total: { label: "Reported total", types: ["aggregate"], color: "text" },
} as const satisfies Record<string, { label: string; types: string[]; color: keyof ChartPalette }>;
export type FundingKind = keyof typeof FUNDING_KINDS;

export const fundingKind = (e: FundingEvent): FundingKind =>
  (Object.keys(FUNDING_KINDS) as FundingKind[]).find((k) =>
    (FUNDING_KINDS[k].types as readonly string[]).includes(e.event_type),
  ) ?? "equity";

/** Where each event came from, in words. */
const SOURCES: Record<string, string> = {
  funding_rounds: "Announced",
  analyst: "Analyst",
  agent: "Research agent",
  uk_sh01: "UK Companies House (SH01)",
  sec_form_d: "SEC Form D",
  cordis_projects: "EU CORDIS",
  people_data_labs: "People Data Labs",
};
export const sourceLabel = (e: FundingEvent) =>
  SOURCES[e.source_name] ?? stageLabel(e.source_name.replaceAll("_", " "));

/** The event's amount in euros, or NaN when it has none (or an unknown currency). */
export const eventEur = (e: FundingEvent) => toEur(e.amount, e.currency) ?? NaN;

export const eventName = (e: FundingEvent) => {
  const programme = e.details?.["programme"];
  if (e.event_type === "eu_grant" && typeof programme === "string") return `EU grant · ${programme}`;
  if (e.round_label) return stageLabel(e.round_label);
  if (e.event_type === "priced_round") return "Priced share allotment";
  if (e.event_type === "form_d") return "Form D filing";
  if (e.event_type === "aggregate") return "Total raised";
  return stageLabel(e.event_type.replaceAll("_", " "));
};

/** The latest total raised a source reports (People Data Labs), if any: one figure, not a round. */
export const reportedTotal = (events: FundingEvent[]) =>
  events.filter((e) => e.event_type === "aggregate" && Number.isFinite(eventEur(e))).at(-1);

/** Who and what, from the event's details: lead investors and notes, investors, or the grant role. */
export function eventDetails(e: FundingEvent): string[] {
  const d = e.details ?? {};
  const text = (key: string) => (typeof d[key] === "string" && d[key] ? (d[key] as string) : null);
  const investors = Array.isArray(d["investors"])
    ? (d["investors"] as unknown[]).filter((i): i is string => typeof i === "string")
    : [];
  return [
    text("lead_investors") && `Lead: ${text("lead_investors")}`,
    investors.length > 0 && `Investors: ${investors.join(", ")}`,
    e.investor_count != null && !investors.length && `${e.investor_count} investors`,
    text("role") && `Role: ${stageLabel(text("role")!.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase())}`,
    text("notes"),
  ].filter((x): x is string => !!x);
}
