import { createFileRoute } from "@tanstack/react-router";
import { Matching } from "../features/pages/Matching";
export const Route = createFileRoute("/matching")({
  validateSearch: (search: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(search).filter(([, v]) => typeof v === "string")) as Record<
      string,
      string
    >,
  head: () => ({
    meta: [
      { title: "Matching — Startup Go" },
      { name: "description", content: "Matching for ocean & deep-tech startup intelligence." },
      { property: "og:title", content: "Matching — Startup Go" },
      {
        property: "og:description",
        content: "Matching for ocean & deep-tech startup intelligence.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Matching,
});
