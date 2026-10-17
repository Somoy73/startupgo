import { createFileRoute } from "@tanstack/react-router";
import { Discover } from "../features/pages/Discover";
export const Route = createFileRoute("/")({
  validateSearch: (search: Record<string, unknown>) =>
    Object.fromEntries(Object.entries(search).filter(([, v]) => typeof v === "string")) as Record<string, string>,
  head: () => ({
    meta: [
      { title: "Discover — Startup Go" },
      { name: "description", content: "Discover ocean & deep-tech startups and search them in plain language." },
      { property: "og:title", content: "Discover — Startup Go" },
      {
        property: "og:description",
        content: "Discover ocean & deep-tech startups and search them in plain language.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Discover,
});
