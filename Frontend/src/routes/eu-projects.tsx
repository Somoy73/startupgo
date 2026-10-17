import { createFileRoute } from "@tanstack/react-router";
import { EuProjects } from "../features/pages/EuProjects";
export const Route = createFileRoute("/eu-projects")({
  head: () => ({
    meta: [
      { title: "EU ocean projects — Startup Go" },
      { name: "description", content: "EU blue-economy projects from CORDIS." },
    ],
  }),
  component: EuProjects,
});
