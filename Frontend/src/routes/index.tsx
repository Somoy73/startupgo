import { createFileRoute } from "@tanstack/react-router";
import { Landing } from "../features/pages/Landing";
export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Home — Startup Go" },
      {
        name: "description",
        content:
          "Startups in Finnish Blue Economy — the newest startups found and assessed by our agentic approach.",
      },
      { property: "og:title", content: "Home — Startup Go" },
      {
        property: "og:description",
        content:
          "Startups in Finnish Blue Economy — the newest startups found and assessed by our agentic approach.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Landing,
});
