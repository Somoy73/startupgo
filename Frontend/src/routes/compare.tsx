import { createFileRoute } from "@tanstack/react-router";
import { Compare } from "../features/pages/Compare";
export const Route = createFileRoute("/compare")({
  validateSearch: (search: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(search).filter(([, v]) => typeof v === "string")) as Record<
      string,
      string
    >,
  head: () => ({
    meta: [
      { title: "Compare — Startup Go" },
      { name: "description", content: "Compare for ocean & deep-tech startup intelligence." },
      { property: "og:title", content: "Compare — Startup Go" },
      {
        property: "og:description",
        content: "Compare for ocean & deep-tech startup intelligence.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Compare,
});
