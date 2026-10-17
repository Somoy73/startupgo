import { createFileRoute } from "@tanstack/react-router";
import { Pipeline } from "../features/pages/Pipeline";
export const Route = createFileRoute("/pipeline")({
  validateSearch: (search: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(search).filter(([, v]) => typeof v === "string")) as Record<
      string,
      string
    >,
  head: () => ({
    meta: [
      { title: "Pipeline — Startup Go" },
      { name: "description", content: "Pipeline for ocean & deep-tech startup intelligence." },
      { property: "og:title", content: "Pipeline — Startup Go" },
      {
        property: "og:description",
        content: "Pipeline for ocean & deep-tech startup intelligence.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Pipeline,
});
