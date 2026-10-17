import { useEffect, useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { DIMENSIONS } from "../api/types";
import type { SearchFilters } from "../lib/discover-search";
import { Button } from "./ui/button";
import { SearchFilterPanel } from "./SearchFilterPanel";
import { PIPELINE_LABELS } from "../lib/format";

const EXAMPLES = [
  "seaweed packaging",
  "carbon capture for ships",
  "kelp forest restoration",
  "ocean data",
];
export function DiscoverSearchBar({
  query,
  filters,
  type,
  busy,
  onSearch,
  onFiltersChange,
  onTypeChange,
  onClear,
}: {
  query: string;
  filters: SearchFilters;
  type: "startups" | "eu-projects";
  busy: boolean;
  onSearch: (query: string) => void;
  onFiltersChange: (filters: SearchFilters) => void;
  onTypeChange: (type: "startups" | "eu-projects") => void;
  onClear: () => void;
}) {
  const [draft, setDraft] = useState(query);
  const [showFilters, setShowFilters] = useState(false);
  useEffect(() => setDraft(query), [query]);
  const euProjects = type === "eu-projects";
  const chips = (["stages", "regions", "sectors", "impactAreas", "pipeline"] as const).flatMap(
    (key) =>
      filters[key].map((value) => ({
        id: `${key}:${value}`,
        label:
          key === "pipeline"
            ? (PIPELINE_LABELS[value as keyof typeof PIPELINE_LABELS] ?? value)
            : value,
        remove: () =>
          onFiltersChange({ ...filters, [key]: filters[key].filter((v) => v !== value) }),
      })),
  );
  for (const d of DIMENSIONS) {
    const level = filters.minLevels[d.key];
    if (level !== undefined)
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
  return (
    <div className="discover-controls">
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
        <Button type="submit" size="icon" title="Search" aria-label="Submit search">
          <Search />
        </Button>
      </form>
      {euProjects ? null : (
        <>
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
            {query && !busy && <span className="small">Matches for “{query}”</span>}
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="rounded-full ml-auto"
              aria-expanded={showFilters}
              aria-controls="discover-filters"
              onClick={() => setShowFilters((v) => !v)}
            >
              <SlidersHorizontal />
              Filters{chips.length > 0 && <span>{chips.length}</span>}
            </Button>
          </div>
          {showFilters && (
            <div id="discover-filters" className="discover-filter-panel">
              <SearchFilterPanel filters={filters} onChange={onFiltersChange} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
