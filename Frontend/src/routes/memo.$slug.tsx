import { createFileRoute } from "@tanstack/react-router";
import { MemoPage } from "../features/pages/MemoPage";
export const Route = createFileRoute("/memo/$slug")({
  head: () => ({
    meta: [
      { title: "Investment memo — Startup Go" },
      { name: "description", content: "One-click investment memo for an ocean & deep-tech startup." },
    ],
  }),
  component: MemoPage,
});
