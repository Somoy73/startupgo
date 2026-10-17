import { createFileRoute } from "@tanstack/react-router";
import { Assess } from "../features/pages/Assess";
export const Route = createFileRoute("/assess/")({
  validateSearch: (search: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(search).filter(([, v]) => typeof v === "string")) as Record<
      string,
      string
    >,
  head: () => ({
    meta: [
      { title: "How we assess — Startup Go" },
      {
        name: "description",
        content:
          "The Startup Go assessment method: KTH Innovation Readiness Level, Ocean Impact Navigator evidence levels and funding momentum, combined into one comparable score.",
      },
      { property: "og:title", content: "How we assess — Startup Go" },
      {
        property: "og:description",
        content:
          "How Startup Go scores readiness, ocean-impact evidence and funding momentum into one comparable investment-potential score.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Assess,
});
