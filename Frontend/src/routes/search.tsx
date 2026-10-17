import { createFileRoute, useRouter } from "@tanstack/react-router";
import { Button } from "../components/ui/button";
import { Search } from "../features/pages/Search";
import { startupListOptions } from "../lib/discover-search";
export const Route = createFileRoute("/search")({
  validateSearch: (search: Record<string, unknown>) => ({
    q: typeof search["q"] === "string" ? search["q"] : "",
    type: search["type"] === "eu-projects" ? "eu-projects" as const : "startups" as const,
    filters: typeof search["filters"] === "string" ? search["filters"] : "",
    sort: typeof search["sort"] === "string" ? search["sort"] : "",
  }),
  loader: ({ context }) => context.queryClient.ensureQueryData(startupListOptions),
  errorComponent: SearchError,
  notFoundComponent: () => <div className="empty">Search is unavailable.</div>,
  head: () => ({
    meta: [
      { title: "Search — Startup Go" },
      {
        name: "description",
        content: "Search startups and EU projects in the Startup Go database.",
      },
      { property: "og:title", content: "Search — Startup Go" },
      {
        property: "og:description",
        content: "Search startups and EU projects in the Startup Go database.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Search,
});
function SearchError() {
  const router = useRouter();
  return <div className="card empty" role="alert"><p>Couldn’t load startups.</p><Button variant="outline" className="mt-3" onClick={() => { void router.invalidate(); }}>Try again</Button></div>;
}
