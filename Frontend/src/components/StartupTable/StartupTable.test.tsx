import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { makeStartup } from "@/lib/fixtures";
import type { Sort } from "@/lib/sort";
import { StartupTable } from "./StartupTable";

const startups = [makeStartup({ slug: "kelp", name: "Kelp Co" })];

const render = (columns: string[], sort: Sort) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <StartupTable startups={startups} columns={columns} sort={sort} onSort={() => {}} onOpen={() => {}} />
    </MemoryRouter>,
  );

const headers = (html: string) => [...html.matchAll(/<th[^>]*>(.*?)<\/th>/g)].map((m) => m[1].replace(/<[^>]+>/g, ""));

describe("StartupTable", () => {
  it("renders the locked name column plus the chosen columns, in registry order", () => {
    const html = render(["potential", "trl"], { key: "potential", dir: "desc" });
    expect(headers(html)).toEqual(["Startup", "TRL", "Investment potential"]);
    expect(html).toContain("Kelp Co");
  });

  it("marks only the active sort column with aria-sort", () => {
    const html = render(["trl", "brl"], { key: "brl", dir: "asc" });
    expect(html.match(/aria-sort="[^"]+"/g)).toEqual(['aria-sort="ascending"']);
    expect(html).toMatch(/<th[^>]*aria-sort="ascending"[^>]*><button[^>]*>BRL/);
  });

  it("renders unsortable headers as plain text", () => {
    const html = render(["sector"], { key: "potential", dir: "desc" });
    expect(html).toMatch(/<th[^>]*>Sector · Country<\/th>/);
    expect(html).not.toMatch(/<button[^>]*>Sector/);
  });
});
