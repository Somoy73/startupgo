import { useState } from "react";
import { SearchBar } from "../../components/SearchBar";
import { ColumnPicker, COLUMNS, DEFAULT_COLUMNS, StartupTable } from "../../components/StartupTable";
import { useNavigate } from "../../lib/navigation";
import { nextSort } from "../../lib/sort";
import { useDiscoverSearch } from "../../lib/useDiscoverSearch";
import { useStoredState } from "../../lib/useStoredState";

const MAX_COMPARE = 3;

// Stored column choices from older versions may name columns that no longer exist.
const knownColumns = (stored: unknown) =>
  Array.isArray(stored) ? stored.filter((id): id is string => COLUMNS.some((c) => c.id === id)) : null;

export function Discover() {
  const navigate = useNavigate();
  const search = useDiscoverSearch();
  const [selected, setSelected] = useState<string[]>([]);
  const [columns, setColumns] = useStoredState("discover.columns", DEFAULT_COLUMNS, knownColumns);
  const { results } = search;

  const toggleCompare = (slug: string) =>
    setSelected((s) => (s.includes(slug) ? s.filter((x) => x !== slug) : s.length < MAX_COMPARE ? [...s, slug] : s));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Discover</h1>
          <p>
            Find startups before they reach your inbox: new registrations, grants, research spin-outs and news,
            classified against your thesis.
          </p>
        </div>
      </div>

      <SearchBar
        query={search.query}
        filters={search.filters}
        interpreting={search.loading && search.searching}
        notice={search.notice}
        onSearch={search.submitQuery}
        onFiltersChange={search.setFilters}
        onClear={search.clear}
      />

      <div className="card">
        {search.hasResponse && results.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-b border-border px-5 py-3">
            <span className="small muted tabular">
              {results.length} startup{results.length === 1 ? "" : "s"}
            </span>
            <div className="ml-auto">
              <ColumnPicker columns={columns} onChange={setColumns} />
            </div>
          </div>
        )}
        {search.error && (
          <p className="empty error">
            {search.searching ? "Search failed" : "Couldn't load startups"}: {search.error}
          </p>
        )}
        {!search.error && search.loading && <p className="empty">Loading…</p>}
        {search.hasResponse && results.length === 0 && (
          <div className="empty">
            <p>No startups match this search.</p>
            <button className="btn mt-3" onClick={search.clear}>
              Clear search
            </button>
          </div>
        )}
        {results.length > 0 && (
          <StartupTable
            startups={results}
            columns={columns}
            sort={search.sort}
            onSort={(key) => search.setSort(nextSort(search.sort, key, search.searching))}
            onOpen={(slug) => navigate(`/startups/${slug}`)}
            selection={{ selected, max: MAX_COMPARE, onToggle: toggleCompare }}
          />
        )}
      </div>
      <p className="small muted mt-2.5">Seed data readiness levels are low-confidence estimates from public sources.</p>

      {selected.length > 0 && (
        <div className="tray" role="region" aria-label="Comparison selection">
          <span className="small">
            {selected.length} of {MAX_COMPARE} selected
          </span>
          <button className="btn" onClick={() => setSelected([])}>
            Clear
          </button>
          <button
            className="btn"
            disabled={selected.length < 2}
            onClick={() => navigate(`/compare?s=${selected.join(",")}`)}
          >
            Compare
          </button>
        </div>
      )}
    </>
  );
}
