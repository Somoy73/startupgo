import { createFileRoute } from "@tanstack/react-router";
import { Methodology } from "../features/pages/Methodology";
export const Route = createFileRoute("/methodology")({
  validateSearch: (search: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(search).filter(([, v]) => typeof v === "string")) as Record<
      string,
      string
    >,
  head: () => ({
    meta: [
      { title: "Methodology — Startup Go" },
      { name: "description", content: "Methodology for ocean & deep-tech startup intelligence." },
      { property: "og:title", content: "Methodology — Startup Go" },
      {
        property: "og:description",
        content: "Methodology for ocean & deep-tech startup intelligence.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Methodology,
});
