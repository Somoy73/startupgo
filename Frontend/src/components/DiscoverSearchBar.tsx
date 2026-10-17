import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import { KTH_DIMENSIONS } from "../api/backend-types";
import type { SearchFilters } from "../lib/discover-search";
import { PIPELINE_LABELS } from "../lib/format";
import { Button } from "./ui/button";

const EXAMPLES = [
  "seaweed packaging",
  "carbon capture for ships",
  "kelp forest restoration",
  "ocean data",
];

interface DiscoverSearchBarProps {
  query: string;
  filters: SearchFilters;
  type: "startups" | "eu-projects";
  busy: boolean;
  onSearch: (query: string) => void;
  onFiltersChange: (filters: SearchFilters) => void;
  onTypeChange: (type: "startups" | "eu-projects") => void;
  onClear: () => void;
}

export function DiscoverSearchBar({
  query,
  filters,
  type,
  busy,
  onSearch,
  onFiltersChange,
  onTypeChange,
  onClear,
}: DiscoverSearchBarProps) {
  const [draft, setDraft] = useState(query);

  useEffect(() => {
    setDraft(query);
  }, [query]);

  const euProjects = type === "eu-projects";

  // Build active filter chips
  const chips = (
    ["stages", "countries", "sectors", "impactAreas", "pipeline"] as const
  ).flatMap((key) =>
    filters[key].map((value) => ({
      id: `${key}:${value}`,
      label:
        key === "pipeline"
          ? PIPELINE_LABELS[value as keyof typeof PIPELINE_LABELS] ?? value
          : value,
      remove: () =>
        onFiltersChange({
          ...filters,
          [key]: filters[key].filter((v) => v !== value),
        }),
    }))
  );

  for (const d of KTH_DIMENSIONS) {
    const level = filters.minLevels[d.key];
    if (level !== undefined) {
      chips.push({
        id: `level:${d.key}`,
        label: `${d.code} ≥ ${level}`,
        remove: () => {
          const minLevels = { ...filters.minLevels };
          delete minLevels[d.key];
          onFiltersChange({ ...filters, minLevels });
        },
      });
    }
  }

  return (
    <div className="discover-controls">
      <div className="discover-mode">
        <Button
          type="button"
          size="sm"
          variant={euProjects ? "default" : "outline"}
          className="rounded-full discover-mode-toggle"
          aria-pressed={euProjects}
          onClick={() => onTypeChange(euProjects ? "startups" : "eu-projects")}
        >
          EU Projects
        </Button>
      </div>

      <form
        role="search"
        className="search-bar discover-input"
        aria-busy={busy}
        onSubmit={(e) => {
          e.preventDefault();
          onSearch(draft.trim());
        }}
      >
        <Search aria-hidden />
        <input
          aria-label="Search text"
          placeholder="Ask in plain language, e.g. seaweed packaging"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoComplete="off"
          enterKeyHint="search"
        />

        {(draft || chips.length > 0) && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            title="Clear search"
            aria-label="Clear search"
            onClick={() => {
              setDraft("");
              onClear();
            }}
          >
            <X />
          </Button>
        )}

        <Button type="submit" className="shrink-0 rounded-full px-4 font-bold">
          <Search aria-hidden />
          AI Search
        </Button>
      </form>

      {!euProjects && (
        <div className="discover-chips" aria-live="polite">
          {busy ? (
            <span className="small">Searching…</span>
          ) : (
            chips.map((chip) => (
              <Button
                key={chip.id}
                variant="secondary"
                size="sm"
                className="rounded-full"
                onClick={chip.remove}
                aria-label={`Remove filter ${chip.label}`}
              >
                {chip.label}
                <X />
              </Button>
            ))
          )}

          {!query &&
            !chips.length &&
            EXAMPLES.map((example) => (
              <Button
                key={example}
                variant="outline"
                size="sm"
                className="rounded-full"
                onClick={() => {
                  setDraft(example);
                  onSearch(example);
                }}
              >
                {example}
              </Button>
            ))}

          {query && !busy && (
            <span className="small">Matches for “{query}”</span>
          )}
        </div>
      )}
    </div>
  );
}