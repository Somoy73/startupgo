import { useEffect, useState } from "react";
import { filterChips, formatSearch, type SearchFilters } from "../lib/search";
import { IconSearch, IconX } from "./Icons";

const EXAMPLES = [
  "seed kelp in europe",
  "trl>=7 brl>=6",
  "carbon capture uk",
  "clean ocean asia",
  "pipeline:diligence",
];

interface Props {
  query: string;
  filters: SearchFilters;
  onQueryChange: (query: string) => void;
}

/** Free-text search that shows what it understood as removable filter chips. */
export function SearchBar({ query, filters, onQueryChange }: Props) {
  const [draft, setDraft] = useState(query);
  useEffect(() => setDraft(query), [query]);

  const chips = filterChips(filters);
  const submit = () => draft.trim() !== query && onQueryChange(draft.trim());

  return (
    <div className="searchbar">
      <form
        role="search"
        className="search"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <IconSearch />
        <label className="visually-hidden" htmlFor="deal-search">
          Search startups
        </label>
        <input
          id="deal-search"
          className="input"
          placeholder="Try “seed kelp in europe trl>=5” or “carbon capture uk”"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={submit}
          autoComplete="off"
        />
        {draft && (
          <button type="button" className="search-clear" aria-label="Clear search" onClick={() => onQueryChange("")}>
            <IconX />
          </button>
        )}
      </form>

      <div className="chips" aria-live="polite">
        {chips.length > 0 ? (
          <>
            <span className="small muted">Understood as:</span>
            {chips.map((chip) => (
              <button
                key={chip.id}
                type="button"
                className="filter-chip"
                onClick={() => onQueryChange(formatSearch(chip.without))}
                aria-label={`Remove filter ${chip.label}`}
              >
                {chip.label}
                <IconX />
              </button>
            ))}
          </>
        ) : (
          <>
            <span className="small muted">Examples:</span>
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" className="example-chip" onClick={() => onQueryChange(ex)}>
                {ex}
              </button>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
