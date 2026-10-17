import { createFileRoute } from "@tanstack/react-router";
import { AssessForm } from "../features/pages/AssessForm";
export const Route = createFileRoute("/assess/$slug")({
  validateSearch: (search: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(search).filter(([, v]) => typeof v === "string")) as Record<
      string,
      string
    >,
  head: () => ({
    meta: [
      { title: "Re-assess a startup — Startup Go" },
      {
        name: "description",
        content: "Record a new readiness and ocean-impact assessment for a startup in your deal flow.",
      },
      { property: "og:title", content: "Re-assess a startup — Startup Go" },
      {
        property: "og:description",
        content: "Record a new readiness and ocean-impact assessment for a startup in your deal flow.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: AssessForm,
});
