import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentScraper } from "@/features/pages/AgentScraper";
import type { ScrapeJob, ScrapeRecord, ScrapeResult } from "@/api/backend-types";

const job = (over: Partial<ScrapeJob>): ScrapeJob => ({
  id: 1,
  status: "queued",
  sources: [],
  created_at: "",
  progress: [],
  result: null,
  error: null,
  ...over,
});

const record = (over: Partial<ScrapeRecord>): ScrapeRecord => ({
  kind: "startup",
  title: "Blue Kelp",
  details: "Grows kelp for feed.",
  website: "https://bluekelp.example",
  attributes: [{ name: "country", value: "Norway" }],
  source_url: "https://pipeline.example/list",
  quote: "Blue Kelp grows kelp for feed",
  evidence: "page",
  self_reported: false,
  group: "BlueInvest pipeline",
  also_in: ["Wellfound startups"],
  ...over,
});

let responses: Record<string, unknown> = {};

describe("AgentScraper", () => {
  const requests: { method: string; path: string; body: unknown }[] = [];

  beforeEach(() => {
    requests.length = 0;
    responses = {
      "GET /api/agent-scrape/info": {
        default: "nvidia",
        models: [
          {
            name: "nvidia",
            provider: "openai-compatible",
            model: "nvidia-test",
            multimodal: true,
            key_set: true,
          },
          {
            name: "gemini",
            provider: "gemini",
            model: "gemini-test",
            multimodal: true,
            key_set: false,
          },
        ],
        web_search: true,
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (path: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        requests.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : null });
        const body = responses[`${method} ${path}`];
        return {
          ok: body !== undefined,
          status: body !== undefined ? 200 : 404,
          statusText: "",
          json: async () => body,
        };
      }),
    );
  });
  afterEach(() => vi.unstubAllGlobals());

  it("runs several preset sources at once with the chosen model", async () => {
    responses["POST /api/agent-scrape"] = job({
      status: "running",
      progress: ["Wellfound startups: Reading https://wellfound.com/startups/industry/aquaculture"],
    });
    render(<AgentScraper />);
    expect(await screen.findByText(/nvidia-test · reads PDFs and images/)).toBeTruthy();
    const menu = screen.getByLabelText("Model") as HTMLSelectElement;
    expect([...menu.options].map((o) => o.text)).toEqual(["NVIDIA (default)", "Gemini"]);
    fireEvent.change(menu, { target: { value: "gemini" } });
    expect(await screen.findByText(/gemini-test .* API key missing/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Wellfound startups" }));
    fireEvent.click(screen.getByRole("button", { name: "CORDIS ocean projects" }));
    expect(
      screen.getByRole("button", { name: "Wellfound startups" }).getAttribute("aria-pressed"),
    ).toBe("true");
    expect(
      screen.getAllByRole("group", { name: /Wellfound startups|CORDIS ocean projects/ }),
    ).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Run agent on 2 sources" }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Wellfound startups: Reading"),
    );
    const sent = requests.at(-1)!;
    expect(sent).toMatchObject({
      method: "POST",
      path: "/api/agent-scrape",
      body: { stealth: true, llm: "gemini" },
    });
    expect((sent.body as { sources: unknown[] }).sources).toMatchObject([
      {
        label: "Wellfound startups",
        mode: "startups",
        urls: ["https://wellfound.com/startups/industry/aquaculture"],
        max_pages: 8,
      },
      {
        label: "CORDIS ocean projects",
        mode: "projects",
        urls: ["https://cordis.europa.eu/search?q=%27blue%20economy%27"],
      },
    ]);
  });

  it("asks for a goal and rejects text that is not a web address before calling the agent", async () => {
    render(<AgentScraper />);
    fireEvent.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Say what the agent should get.");

    fireEvent.change(screen.getByLabelText("Goal"), { target: { value: "find funds" } });
    fireEvent.change(screen.getByLabelText(/^URLs/), { target: { value: "localhost" } });
    fireEvent.click(screen.getByRole("button", { name: "Run agent" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Not a web address: localhost");
    expect(requests.some((r) => r.method === "POST")).toBe(false);
  });

  it("adds a scraped startup to the database, asking for a website when it has none", async () => {
    const result: ScrapeResult = {
      goal: "g",
      summary: "",
      groups: [
        {
          label: "BlueInvest pipeline",
          goal: "g",
          mode: "startups",
          summary: "Two startups.",
          records: 2,
          error: null,
        },
        {
          label: "Wellfound startups",
          goal: "g",
          mode: "startups",
          summary: "",
          records: 0,
          error: "blocked",
        },
      ],
      records: [
        record({}),
        record({ title: "Wave Co", website: "", also_in: [], self_reported: true }),
      ],
      gaps: [],
      sources: [],
      notices: [],
      model: "m",
      usage: "u",
    };
    responses["POST /api/agent-scrape"] = job({ status: "done", result });
    responses["POST /api/agent-scrape/startups"] = {
      slug: "blue-kelp",
      name: "Blue Kelp",
      status: "created",
    };
    render(<AgentScraper />);
    fireEvent.change(screen.getByLabelText("Goal"), { target: { value: "ocean startups" } });
    fireEvent.click(screen.getByRole("button", { name: "Run agent" }));

    expect(await screen.findByText("2 records from 2 sources")).toBeTruthy();
    expect(screen.getByText(/nothing read: blocked/)).toBeTruthy();
    expect(screen.getByText("Also in Wellfound startups")).toBeTruthy();
    expect(screen.getByText("Self-reported")).toBeTruthy();

    const [blueKelp, waveCo] = screen.getAllByRole("button", { name: "Add to DB" });
    expect((waveCo as HTMLButtonElement).disabled).toBe(true); // no website yet
    fireEvent.change(screen.getByLabelText("Website of Wave Co"), {
      target: { value: "waveco.example" },
    });
    expect((waveCo as HTMLButtonElement).disabled).toBe(false);

    fireEvent.click(blueKelp!);
    const link = await screen.findByRole("link", { name: "Open Blue Kelp →" });
    expect(link.getAttribute("href")).toBe("/startups/blue-kelp");
    expect(within(link.parentElement!).getByText("Added to the database")).toBeTruthy();
    expect(requests.at(-1)).toMatchObject({
      method: "POST",
      path: "/api/agent-scrape/startups",
      body: { record: { title: "Blue Kelp", website: "https://bluekelp.example" } },
    });
  });
});
