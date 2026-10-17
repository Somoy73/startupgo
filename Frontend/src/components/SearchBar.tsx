import { useEffect, useState } from "react";
import { filterChips, type SearchFilters } from "../lib/search";
import { IconSearch, IconX } from "./Icons";

const EXAMPLES = [
  "early-stage seaweed startups in the nordics",
  "proven tech fighting plastic pollution",
  "climate startups ready for a series a",
  "deals in diligence with trl>=7",
];

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
 * Natural-language search. The backend's search returns the filters it applied; they're
 * shown as chips, and removing one re-runs the search with the edited filters.
 */
export function SearchBar({ query, filters, interpreted, interpreting, notice, onSearch, onFiltersChange, onClear }: Props) {
  const [draft, setDraft] = useState(query);
  useEffect(() => setDraft(query), [query]);

  const chips = filters ? filterChips(filters) : [];
  const search = (text: string) => {
    setDraft(text);
    if (text.trim() !== query) onSearch(text.trim());
  };

  return (
    <div className="searchbar">
      <form
        role="search"
        className="search"
        aria-busy={interpreting}
        onSubmit={(e) => {
          e.preventDefault();
          search(draft);
        }}
      >
        <IconSearch />
        <label className="visually-hidden" htmlFor="deal-search">
          Search startups
        </label>
        <input
          id="deal-search"
          className="input"
          placeholder="Ask in plain language, e.g. “seed-stage kelp startups in the nordics with proven tech”"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          autoComplete="off"
          enterKeyHint="search"
        />
        {(draft || chips.length > 0) && (
          <button
            type="button"
            className="search-clear"
            aria-label="Clear search"
            onClick={() => {
              setDraft("");
              onClear();
            }}
          >
            <IconX />
          </button>
        )}
      </form>

      <div className="chips" aria-live="polite">
        {interpreting ? (
          <span className="small muted">Searching…</span>
        ) : chips.length > 0 && filters ? (
          <>
            <span className="small muted">
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
                className="filter-chip"
                onClick={() => onFiltersChange(chip.without)}
                aria-label={`Remove filter ${chip.label}`}
              >
                {chip.label}
                <IconX />
              </button>
            ))}
            {notice && <span className="small muted">{notice}</span>}
          </>
        ) : (
          <>
            <span className="small muted">Examples:</span>
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" className="example-chip" onClick={() => search(ex)}>
                {ex}
              </button>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
