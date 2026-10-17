import type { ScrapeMode, ScrapeRecord, ScrapeRecordKind } from "../api/backend-types";

/** A one-click source for the scraper: its goal, URLs and focus prompt, which stay editable. */
export type ScrapePreset = {
  id: string;
  label: string;
  mode: ScrapeMode;
  goal: string;
  urls: string[];
  /** Shown when the preset needs something from the user, such as a link to paste. */
  hint?: string;
  followLinks?: boolean;
};

export const SCRAPE_PRESETS: ScrapePreset[] = [
  {
    id: "blue-list",
    mode: "startups",
    label: "Blue List companies",
    urls: ["https://blue-list.net/Orgs"],
    goal: "List the ocean technology companies in the Blue List directory: name and website. Skip the news sites, funders and accelerators it also lists.",
  },
  {
    id: "blueinvest",
    mode: "startups",
    label: "BlueInvest pipeline",
    urls: ["https://blueinvest-community.converve.io/pipeline_front.html"],
    goal: "List the blue economy startups and scaleups in the BlueInvest community pipeline: name, country, sector, what they do, TRL and funding stage.",
    followLinks: true, // the list shows project titles; each profile's detail page names the company
  },
  {
    id: "top-tier-impact",
    mode: "startups",
    label: "Blue economy startup list",
    urls: ["https://www.toptierimpact.com/blue-economy-startups"],
    goal: "List the blue economy startups in Top Tier Impact's global list: name, country and the segment it is listed under (seafood and aquaculture, cleanup, marine energy, ...).",
  },
  {
    id: "hatch-blue",
    mode: "startups",
    label: "Hatch Blue portfolio",
    urls: ["https://www.hatch.blue/portfolio"],
    goal: "List the aquaculture and seafood startups in Hatch Blue's portfolio: name, country, fund or programme, and what they do.",
  },
  {
    id: "wellfound",
    mode: "startups",
    label: "Wellfound startups",
    urls: ["https://wellfound.com/startups/industry/aquaculture"],
    goal: "List the startups on this page: name, website, one-line pitch, stage, market tags and location.",
  },
  {
    id: "cordis",
    mode: "projects",
    label: "CORDIS ocean projects",
    urls: ["https://cordis.europa.eu/search?q=%27blue%20economy%27"],
    goal: "List the EU-funded blue economy and ocean projects: title, acronym, coordinator, countries, EU contribution, start and end dates, and what the project does in one sentence.",
  },
  {
    id: "funding-news",
    mode: "funding_rounds",
    label: "Funding news",
    urls: [],
    goal: "Find recent funding rounds of European ocean and blue-economy startups: company, round, amount, investors and date.",
    hint: "No URL: the agent searches the web for this.",
  },
  {
    id: "company",
    mode: "company",
    label: "Company profile",
    urls: [],
    goal: "What the company does, its team and roles, headcount, funding raised and investors, customers or pilots, and recent news.",
    hint: "Paste the company's website or profile pages below (LinkedIn, Crunchbase, news). Pages behind a login come back empty and are listed as gaps.",
    followLinks: true,
  },
  {
    id: "report",
    mode: "document",
    label: "Report or deck (PDF)",
    urls: [],
    goal: "From this document: company, revenue and result by year, headcount, funding, customers, risks and plans.",
    hint: "Paste the PDF link below. Reading PDFs and images needs a multimodal agent.",
  },
];

export type ParsedUrls = { urls: string[]; invalid: string[] };

/** URLs from free text (one per line, or separated by spaces or commas); a bare domain gets https://. */
export function parseUrls(text: string): ParsedUrls {
  const urls: string[] = [];
  const invalid: string[] = [];
  for (const token of text.split(/[\s,]+/).filter(Boolean)) {
    const candidate = /^[a-z][a-z0-9+.-]*:(?!\d)/i.test(token) ? token : `https://${token}`;
    try {
      const url = new URL(candidate);
      if ((url.protocol !== "http:" && url.protocol !== "https:") || !url.hostname.includes(".")) {
        throw new Error("not a web address");
      }
      if (!urls.includes(candidate)) urls.push(candidate);
    } catch {
      invalid.push(token);
    }
  }
  return { urls, invalid };
}

function csvCell(value: string): string {
  return /[",\n\r]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** The records as CSV: source, kind, title, details, website, evidence, then one column per attribute name. */
export function recordsToCsv(records: ScrapeRecord[]): string {
  const names = [...new Set(records.flatMap((r) => r.attributes.map((a) => a.name)))];
  const header = [
    "source",
    "kind",
    "title",
    "details",
    "website",
    "evidence",
    "self_reported",
    "also_in",
    "source_url",
    "quote",
    ...names,
  ];
  const rows = records.map((r) => [
    r.group,
    r.kind,
    r.title,
    r.details,
    r.website,
    r.evidence,
    r.self_reported ? "yes" : "",
    r.also_in.join("; "),
    r.source_url,
    r.quote,
    ...names.map((n) =>
      r.attributes
        .filter((a) => a.name === n)
        .map((a) => a.value)
        .join("; "),
    ),
  ]);
  return [header, ...rows].map((row) => row.map(csvCell).join(",")).join("\n");
}

/** What each focus prompt reads for, as shown in the source's Focus menu. */
export const MODE_LABELS: Record<ScrapeMode, string> = {
  general: "Anything",
  startups: "Startups and companies",
  funding_calls: "Funding calls and grants",
  projects: "EU and research projects",
  funding_rounds: "Funding rounds and investors",
  company: "One company in depth",
  document: "Report, deck or paper",
};

export const KIND_LABELS: Record<ScrapeRecordKind, string> = {
  startup: "Startup",
  company: "Company",
  funding_call: "Funding call",
  project: "Project",
  funding_round: "Funding round",
  investor: "Investor",
  figure: "Figure",
  other: "Other",
};

/** Records the user can add to the database as a startup. */
export const canAddToDb = (record: ScrapeRecord) =>
  record.kind === "startup" || record.kind === "company";

/** A source being edited on the page; ``presetId`` links it to its preset button. */
export type SourceDraft = {
  key: number;
  presetId: string | null;
  label: string;
  goal: string;
  urlText: string;
  followLinks: boolean;
  mode: ScrapeMode;
  hint: string | null;
};

let nextKey = 1;

export function draftFromPreset(preset: ScrapePreset): SourceDraft {
  return {
    key: nextKey++,
    presetId: preset.id,
    label: preset.label,
    goal: preset.goal,
    urlText: preset.urls.join("\n"),
    followLinks: preset.followLinks ?? false,
    mode: preset.mode,
    hint: preset.hint ?? null,
  };
}

export function emptyDraft(label = "Custom source"): SourceDraft {
  return {
    key: nextKey++,
    presetId: null,
    label,
    goal: "",
    urlText: "",
    followLinks: false,
    mode: "general",
    hint: null,
  };
}

const isBlank = (d: SourceDraft) => !d.presetId && !d.goal.trim() && !d.urlText.trim();

/** The sources after a preset button is pressed: removes its source, or adds it (replacing an untouched blank one). */
export function togglePreset(drafts: SourceDraft[], preset: ScrapePreset): SourceDraft[] {
  if (drafts.some((d) => d.presetId === preset.id)) {
    const rest = drafts.filter((d) => d.presetId !== preset.id);
    return rest.length ? rest : [emptyDraft()];
  }
  return [...drafts.filter((d) => !isBlank(d)), draftFromPreset(preset)];
}
