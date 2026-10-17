import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppHeader } from "@/components/AppHeader";

function renderAt(path: string) {
  const rootRoute = createRootRoute({ component: AppHeader });
  const routes = ["/", "/search", "/agent-scraper"].map((p) =>
    createRoute({ getParentRoute: () => rootRoute, path: p, component: () => null }),
  );
  const router = createRouter({
    routeTree: rootRoute.addChildren(routes),
    history: createMemoryHistory({ initialEntries: [path] }),
  });
  render(<RouterProvider router={router} />);
}

describe("AppHeader", () => {
  it.each(["/", "/search"])(
    "links to the agent scraper as the last header item on %s",
    async (path) => {
      renderAt(path);
      const link = await screen.findByRole("link", { name: "Agent Scraper" });
      expect(link.getAttribute("href")).toBe("/agent-scraper");
      const inner = link.parentElement!;
      const items = [...inner.children].filter((el) => !el.classList.contains("menu-toggle"));
      expect(items.at(-1)).toBe(link); // right-most, before only the mobile menu toggle
    },
  );

  it("marks the button active on the agent scraper page", async () => {
    renderAt("/agent-scraper");
    expect((await screen.findByRole("link", { name: "Agent Scraper" })).className).toContain(
      "active",
    );
  });
});
