import { useEffect, useState } from "react";
import { LuSearch, LuSlidersHorizontal, LuX } from "react-icons/lu";
import { emptyFilters, filterChips, type SearchFilters } from "@/lib/search";
import { SearchFilterPanel } from "./SearchFilterPanel";

const EXAMPLES = [
  "early-stage seaweed startups in the nordics",
  "proven tech fighting plastic pollution",
  "climate startups ready for a series a",
  "deals in diligence with trl>=7",
];

const CHIP = "inline-flex cursor-pointer items-center gap-1 rounded-full border py-0.75 pl-2.5 text-sm";
const FILTER_CHIP = `${CHIP} border-transparent bg-accent-wash pr-2 font-semibold text-accent-ink hover:border-accent`;
const EXAMPLE_CHIP = `${CHIP} border-line bg-transparent pr-2.5 text-fg-2 hover:bg-surface-2`;
const NOTE = "text-small text-muted";
// Chips that aren't free-text keywords: what the Filters panel edits.
const isStructured = (chipId: string) => !chipId.startsWith("text:") && !chipId.startsWith("anyText:");

interface Props {
  /** What the user last searched for (the `q` URL parameter). */
  query: string;
  /** Filters the backend applied, or null before the first response. */
  filters: SearchFilters | null;
  /** True when `filters` are what the search derived from `query` (not edited chips). */
  interpreted: boolean;
  interpreting: boolean;
  /** Shown next to the chips, e.g. when the search fell back to keyword matching. */
  notice: string | null;
  onSearch: (query: string) => void;
  onFiltersChange: (filters: SearchFilters) => void;
  onClear: () => void;
}

/**
 * Natural-language search on one island: the input, the filters the search applied (as
 * removable chips) and a Filters panel to edit them directly. Editing filters re-runs the
 * search with the edited filters.
 */
export function SearchBar({
  query,
  filters,
  interpreted,
  interpreting,
  notice,
  onSearch,
  onFiltersChange,
  onClear,
}: Props) {
  const [draft, setDraft] = useState(query);
  const [showFilters, setShowFilters] = useState(false);
  useEffect(() => setDraft(query), [query]);

  const chips = filters ? filterChips(filters) : [];
  const activeFilters = chips.filter((c) => isStructured(c.id)).length;
  const search = (text: string) => {
    setDraft(text);
    if (text.trim() !== query) onSearch(text.trim());
  };

  return (
    <div className="mb-4 rounded-island border border-line bg-surface px-4 pt-3.5 pb-3 shadow-card">
      <form
        role="search"
        className="relative"
        aria-busy={interpreting}
        onSubmit={(e) => {
          e.preventDefault();
          search(draft);
        }}
      >
        <LuSearch className="absolute top-1/2 left-3 size-4.5 -translate-y-1/2 text-muted" />
        <label className="sr-only" htmlFor="deal-search">
          Search startups
        </label>
        <input
          id="deal-search"
          // Recessed into the island: page colour rather than the island's surface.
          className="w-full min-w-0 rounded-card border border-line bg-page px-9.5 py-2.75 text-base focus:outline-2 focus:outline-offset-1 focus:outline-accent"
          placeholder="Ask in plain language..."
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoComplete="off"
          enterKeyHint="search"
        />
        {(draft || chips.length > 0) && (
          <button
            type="button"
            className="absolute top-1/2 right-2 grid -translate-y-1/2 cursor-pointer place-items-center rounded-md border-0 bg-transparent p-1.5 text-muted hover:bg-surface-2 hover:text-fg"
            aria-label="Clear search"
            onClick={() => {
              setDraft("");
              onClear();
            }}
          >
            <LuX size={14} />
          </button>
        )}
      </form>

      <div className="mt-2.5 flex min-h-7 flex-wrap items-center gap-1.5" aria-live="polite">
        {interpreting ? (
          <span className={NOTE}>Searching…</span>
        ) : chips.length > 0 && filters ? (
          <>
            <span className={NOTE}>
              {interpreted && query ? (
                <>
                  Interpreted <q>{query}</q> as:
                </>
              ) : (
                "Filters:"
              )}
            </span>
            {chips.map((chip) => (
              <button
                key={chip.id}
                type="button"
                className={FILTER_CHIP}
                onClick={() => onFiltersChange(chip.without)}
                aria-label={`Remove filter ${chip.label}`}
              >
                {chip.label}
                <LuX size={14} />
              </button>
            ))}
            {notice && <span className={NOTE}>{notice}</span>}
          </>
        ) : (
          <>
            <span className={NOTE}>Examples:</span>
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" className={EXAMPLE_CHIP} onClick={() => search(ex)}>
                {ex}
              </button>
            ))}
          </>
        )}
        <button
          type="button"
          className={`ml-auto inline-flex cursor-pointer items-center gap-1.5 rounded-full border py-0.75 pr-2.5 pl-2 text-sm ${
            showFilters || activeFilters
              ? "border-accent bg-accent-wash text-accent-ink"
              : "border-line bg-transparent text-fg-2 hover:bg-surface-2"
          }`}
          aria-expanded={showFilters}
          aria-controls="search-filters"
          onClick={() => setShowFilters((v) => !v)}
        >
          <LuSlidersHorizontal size={13} />
          Filters
          {activeFilters > 0 && <span className="font-semibold tabular-nums">{activeFilters}</span>}
        </button>
      </div>

      {showFilters && (
        <div id="search-filters">
          <SearchFilterPanel filters={filters ?? emptyFilters()} onChange={onFiltersChange} />
        </div>
      )}
    </div>
  );
}
