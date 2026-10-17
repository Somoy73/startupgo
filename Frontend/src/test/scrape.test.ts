import { describe, expect, it } from "vitest";

import type { ScrapeRecord } from "@/api/backend-types";
import {
  MODE_LABELS,
  SCRAPE_PRESETS,
  emptyDraft,
  parseUrls,
  recordsToCsv,
  togglePreset,
} from "@/lib/scrape";

describe("parseUrls", () => {
  it("accepts one URL per line or separated by commas, adds https:// to bare domains and drops duplicates", () => {
    const { urls, invalid } = parseUrls(
      "cordis.europa.eu/search?q=blue\nhttps://a.example/x.pdf, https://a.example/x.pdf\n\n",
    );
    expect(urls).toEqual(["https://cordis.europa.eu/search?q=blue", "https://a.example/x.pdf"]);
    expect(invalid).toEqual([]);
  });

  it("reports what is not a web address", () => {
    expect(parseUrls("ftp://a.example/file localhost mailto:x@y.example").invalid).toEqual([
      "ftp://a.example/file",
      "localhost",
      "mailto:x@y.example",
    ]);
  });
});

describe("recordsToCsv", () => {
  const record = (over: Partial<ScrapeRecord>): ScrapeRecord => ({
    kind: "funding_call",
    website: "",
    self_reported: false,
    group: "Calls",
    also_in: [],
    title: "Blue Call",
    details: "Open, 12 M",
    attributes: [],
    source_url: "https://a.example/",
    quote: 'closes "soon"',
    evidence: "page",
    ...over,
  });

  it("has one column per attribute name and quotes cells that need it", () => {
    const csv = recordsToCsv([
      record({ attributes: [{ name: "deadline", value: "30 March" }] }),
      record({
        title: "Other",
        group: "News",
        also_in: ["Calls"],
        attributes: [
          { name: "budget", value: "EUR 1M" },
          { name: "budget", value: "EUR 2M" },
        ],
      }),
    ]);
    expect(csv.split("\n")).toEqual([
      "source,kind,title,details,website,evidence,self_reported,also_in,source_url,quote,deadline,budget",
      'Calls,funding_call,Blue Call,"Open, 12 M",,page,,,https://a.example/,"closes ""soon""",30 March,',
      'News,funding_call,Other,"Open, 12 M",,page,,Calls,https://a.example/,"closes ""soon""",,EUR 1M; EUR 2M',
    ]);
  });
});

describe("SCRAPE_PRESETS", () => {
  it("have unique ids and only valid URLs", () => {
    expect(new Set(SCRAPE_PRESETS.map((p) => p.id)).size).toBe(SCRAPE_PRESETS.length);
    for (const preset of SCRAPE_PRESETS) {
      expect(parseUrls(preset.urls.join("\n")).invalid).toEqual([]);
      expect(preset.goal.length).toBeGreaterThan(20);
    }
  });
});

describe("togglePreset", () => {
  const [blueList, blueinvest] = SCRAPE_PRESETS;

  it("replaces the untouched blank source, adds further presets, and removes a pressed one", () => {
    let drafts = togglePreset([emptyDraft()], blueList!);
    expect(drafts.map((d) => d.presetId)).toEqual(["blue-list"]);
    expect(drafts[0]).toMatchObject({ mode: "startups", label: "Blue List companies" });

    drafts = togglePreset(drafts, blueinvest!);
    expect(drafts.map((d) => d.presetId)).toEqual(["blue-list", "blueinvest"]);

    drafts = togglePreset(drafts, blueList!);
    expect(drafts.map((d) => d.presetId)).toEqual(["blueinvest"]);
    drafts = togglePreset(drafts, blueinvest!);
    expect(drafts.map((d) => d.presetId)).toEqual([null]); // never no source at all
  });

  it("keeps a custom source the user has typed in", () => {
    const typed = { ...emptyDraft(), goal: "my own goal" };
    expect(togglePreset([typed], blueList!).map((d) => d.presetId)).toEqual([null, "blue-list"]);
  });
});

describe("presets", () => {
  it("each have a focus prompt", () => {
    for (const preset of SCRAPE_PRESETS) expect(MODE_LABELS[preset.mode]).toBeTruthy();
  });
});
