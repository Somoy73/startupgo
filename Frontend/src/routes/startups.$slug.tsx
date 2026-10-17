import { createFileRoute } from "@tanstack/react-router";
import { StartupPage } from "../features/pages/StartupPage";
export const Route = createFileRoute("/startups/$slug")({
  validateSearch: (search: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(search).filter(([, v]) => typeof v === "string")) as Record<
      string,
      string
    >,
  head: () => ({
    meta: [
      { title: "Startup profile — Startup Go" },
      {
        name: "description",
        content: "Startup profile for ocean & deep-tech startup intelligence.",
      },
      { property: "og:title", content: "Startup profile — Startup Go" },
      {
        property: "og:description",
        content: "Startup profile for ocean & deep-tech startup intelligence.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: StartupPage,
});
