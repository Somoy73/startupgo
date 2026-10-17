import { useEffect, useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { filterChips, type SearchFilters } from "../lib/search";
import { cn } from "../lib/utils";
import { SearchFilterPanel } from "./SearchFilterPanel";

const EXAMPLES = ["seaweed packaging", "carbon capture for ships", "kelp forest restoration", "ocean data"];

const CHIP = "inline-flex cursor-pointer items-center gap-1 rounded-full border px-3 py-1 text-xs";
const FILTER_CHIP = cn(CHIP, "border-transparent bg-wash font-bold text-primary hover:border-primary");
const EXAMPLE_CHIP = cn(CHIP, "border-border bg-transparent text-muted-foreground hover:bg-wash");
const NOTE = "text-xs text-muted-foreground";
// Chips that aren't free-text terms: what the Filters panel edits.
const isStructured = (chipId: string) => !chipId.startsWith("text:") && !chipId.startsWith("anyText:");

type Props = {
  /** What the user last searched for (the `q` URL parameter). */
  query: string;
  /** Active filters, shown as chips and edited in the Filters panel. */
  filters: SearchFilters;
  interpreting: boolean;
  /** Shown next to the chips, e.g. matches not in the database yet. */
  notice: string | null;
  onSearch: (query: string) => void;
  onFiltersChange: (filters: SearchFilters) => void;
  onClear: () => void;
};

/**
 * Natural-language search on one island: the input, the active filters as removable chips,
 * and a Filters panel to edit them. Filters refine the results without re-running the search.
 */
export function SearchBar({ query, filters, interpreting, notice, onSearch, onFiltersChange, onClear }: Props) {
  const [draft, setDraft] = useState(query);
  const [showFilters, setShowFilters] = useState(false);
  useEffect(() => setDraft(query), [query]);

  const chips = filterChips(filters);
  const activeFilters = chips.filter((c) => isStructured(c.id)).length;
  const search = (text: string) => {
    setDraft(text);
    if (text.trim() !== query) onSearch(text.trim());
  };

  return (
    <div className="my-6 rounded-xl border border-border bg-card p-4 shadow-card">
      <form
        role="search"
        className="flex items-center gap-3 rounded-full border border-input bg-background px-5 py-3 focus-within:ring-2 focus-within:ring-ring"
        aria-busy={interpreting}
        onSubmit={(e) => {
          e.preventDefault();
          search(draft);
        }}
      >
        <Search aria-hidden className="size-5 shrink-0 text-muted-foreground" />
        <label className="sr-only" htmlFor="discover-search">
          Search startups
        </label>
        <input
          id="discover-search"
          className="w-full min-w-0 bg-transparent outline-none"
          placeholder="Ask in plain language, e.g. “seaweed packaging replacing plastic”"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoComplete="off"
          enterKeyHint="search"
        />
        {(draft || chips.length > 0) && (
          <button
            type="button"
            className="grid shrink-0 cursor-pointer place-items-center rounded-full p-1.5 text-muted-foreground hover:bg-wash hover:text-foreground"
            aria-label="Clear search"
            onClick={() => {
              setDraft("");
              onClear();
            }}
          >
            <X aria-hidden className="size-4" />
          </button>
        )}
      </form>

      <div className="mt-3 flex min-h-8 flex-wrap items-center gap-1.5" aria-live="polite">
        {interpreting ? (
          <span className={NOTE}>Searching…</span>
        ) : chips.length > 0 ? (
          <>
            <span className={NOTE}>Filters:</span>
            {chips.map((chip) => (
              <button
                key={chip.id}
                type="button"
                className={FILTER_CHIP}
                onClick={() => onFiltersChange(chip.without)}
                aria-label={`Remove filter ${chip.label}`}
              >
                {chip.label}
                <X aria-hidden className="size-3" />
              </button>
            ))}
            {notice && <span className={NOTE}>{notice}</span>}
          </>
        ) : query ? (
          <span className={NOTE}>
            Matches for <q>{query}</q>, most relevant first.{notice && ` ${notice}`}
          </span>
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
          className={cn(
            CHIP,
            "ml-auto gap-1.5",
            showFilters || activeFilters
              ? "border-primary bg-wash text-primary"
              : "border-border bg-transparent text-muted-foreground hover:bg-wash",
          )}
          aria-expanded={showFilters}
          aria-controls="discover-filters"
          onClick={() => setShowFilters((v) => !v)}
        >
          <SlidersHorizontal aria-hidden className="size-3.5" />
          Filters
          {activeFilters > 0 && <span className="font-bold tabular-nums">{activeFilters}</span>}
        </button>
      </div>

      {showFilters && (
        <div id="discover-filters">
          <SearchFilterPanel filters={filters} onChange={onFiltersChange} />
        </div>
      )}
    </div>
  );
}
