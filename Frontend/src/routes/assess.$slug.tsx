import { createFileRoute } from "@tanstack/react-router";
import { Assess } from "../features/pages/Assess";
export const Route = createFileRoute("/assess/$slug")({
  validateSearch: (search: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(search).filter(([, v]) => typeof v === "string")) as Record<
      string,
      string
    >,
  head: () => ({
    meta: [
      { title: "Assess — Startup Go" },
      { name: "description", content: "Assess for ocean & deep-tech startup intelligence." },
      { property: "og:title", content: "Assess — Startup Go" },
      { property: "og:description", content: "Assess for ocean & deep-tech startup intelligence." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Assess,
});
