import { createFileRoute } from "@tanstack/react-router";
import { AgentScraper } from "../features/pages/AgentScraper";
export const Route = createFileRoute("/agent-scraper")({
  head: () => ({
    meta: [
      { title: "Agent scraper - Startup Go" },
      {
        name: "description",
        content: "Ask the agent to read pages, PDFs and images and return source-checked records.",
      },
    ],
  }),
  component: AgentScraper,
});
