import { createFileRoute } from "@tanstack/react-router";
import { DealFlow } from "../features/pages/DealFlow";
export const Route = createFileRoute("/")({
  validateSearch: (search: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(search).filter(([, v]) => typeof v === "string")) as Record<
      string,
      string
    >,
  head: () => ({
    meta: [
      { title: "Deal flow — Startup Go" },
      { name: "description", content: "Deal flow for ocean & deep-tech startup intelligence." },
      { property: "og:title", content: "Deal flow — Startup Go" },
      {
        property: "og:description",
        content: "Deal flow for ocean & deep-tech startup intelligence.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: DealFlow,
});
