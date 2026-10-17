import { useEffect, useState } from "react";

/** What the search is doing, by seconds since it started (LightRAG: parse the query, walk the graph, rank). */
const SEARCH_STEPS: { after: number; label: string }[] = [
  { after: 0, label: "Understanding your query…" },
  { after: 2, label: "Searching the knowledge graph…" },
  { after: 5, label: "Ranking matches…" },
  { after: 15, label: "Still working. Complex queries can take up to a minute." },
];

/**
 * A moving bar and a status line for a request in progress. With `steps`, the line walks through
 * the search's stages as time passes; remount it (key) to restart the clock for a new request.
 */
export function SearchProgress({ label, steps = false }: { label?: string; steps?: boolean }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!steps) return;
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [steps]);
  const step = SEARCH_STEPS.filter((s) => seconds >= s.after).at(-1)?.label;

  return (
    <div role="status" className="flex flex-col gap-2 border-b border-border px-5 py-3.5">
      <div className="search-progress" aria-hidden />
      <span className="small muted">{steps ? step : label}</span>
    </div>
  );
}
