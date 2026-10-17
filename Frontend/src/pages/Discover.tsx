import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { StartupSummary } from "@/api/types";
import { SearchBar } from "@/components/SearchBar";
import { ColumnPicker, COLUMNS, DEFAULT_COLUMNS, StartupTable } from "@/components/StartupTable";
import { button, card, control, cx, EmptyState, PageHeader, StatCard } from "@/components/ui";
import { compactMoney, score } from "@/lib/format";
import { isEmpty } from "@/lib/search";
import { isSortKey, nextSort, SORTS } from "@/lib/sort";
import { useDealFlowSearch } from "@/lib/useDealFlowSearch";
import { useStoredState } from "@/lib/useStoredState";

const MAX_COMPARE = 3;
// The tray is dark-on-light inverted, so its buttons set their own text colour.
const TRAY_BUTTON = cx(button(), "text-fg");

// Stored column choices from older versions may name columns that no longer exist.
const knownColumns = (stored: unknown) =>
  Array.isArray(stored) ? stored.filter((id): id is string => COLUMNS.some((c) => c.id === id)) : null;

export function Discover() {
  const navigate = useNavigate();
  const search = useDealFlowSearch();
  const [selected, setSelected] = useState<string[]>([]);
  const { results } = search;
  const [columns, setColumns] = useStoredState("discover.columns", DEFAULT_COLUMNS, knownColumns);

  const toggleCompare = (slug: string) =>
    setSelected((s) => (s.includes(slug) ? s.filter((x) => x !== slug) : s.length < MAX_COMPARE ? [...s, slug] : s));

  return (
    <>
      <PageHeader
        title="Discover"
        description="Find startups before they reach your inbox: new registrations, grants, research spin-outs and news, classified against your thesis."
      />

      {/* <Stats startups={results} filtered={!isEmpty(search.filters)} /> */}

      <SearchBar
        query={search.query}
        filters={search.filters}
        interpreting={search.interpreting}
        notice={search.notice}
        onSearch={search.submitQuery}
        onFiltersChange={search.setFilters}
        onClear={search.clear}
      />

      <div className={card}>
        {search.hasResponse && results.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 border-b border-grid px-3 py-2.5">
            <span className="text-small text-muted tabular-nums">
              {results.length} startup{results.length === 1 ? "" : "s"}
            </span>
            <div className="ml-auto flex items-center gap-2">
              {/* Phones show cards without headers, so sorting needs a menu there. */}
              <label className="sr-only" htmlFor="sort">
                Sort by
              </label>
              <select
                id="sort"
                className={cx(control, "md:hidden")}
                value={search.sort.key}
                onChange={(e) =>
                  isSortKey(e.target.value) &&
                  search.setSort({ key: e.target.value, dir: SORTS[e.target.value].defaultDir })
                }
              >
                {Object.entries(SORTS)
                  .filter(([key]) => key !== "relevance" || search.searching)
                  .map(([key, { label }]) => (
                    <option key={key} value={key}>
                      Sort: {label}
                    </option>
                  ))}
              </select>
              <ColumnPicker columns={columns} onChange={setColumns} />
            </div>
          </div>
        )}
        {search.error && (
          <EmptyState error>
            {search.searching ? "Search failed" : "Couldn't load startups"}: {search.error}
          </EmptyState>
        )}
        {!search.error && search.loading && <EmptyState>Loading…</EmptyState>}
        {!search.error && search.hasResponse && results.length === 0 && (
          <div className="p-10 text-center text-muted">
            <p>No startups match this search.</p>
            <button className={cx(button(), "mt-3")} onClick={search.clear}>
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
      <p className="mt-2.5 text-small text-muted">
        Seed data readiness levels are low-confidence estimates from public sources. Use Assess to record your own.
      </p>

      {selected.length > 0 && (
        <div
          className="fixed bottom-5 left-1/2 z-20 flex max-w-[calc(100vw-32px)] -translate-x-1/2 items-center gap-3 rounded-xl bg-fg py-2.5 pr-3 pl-4.5 text-page shadow-float"
          role="region"
          aria-label="Comparison selection"
        >
          <span className="text-small">
            {selected.length} of {MAX_COMPARE} selected
          </span>
          <button className={TRAY_BUTTON} onClick={() => setSelected([])}>
            Clear
          </button>
          <button
            className={TRAY_BUTTON}
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

function Stats({ startups, filtered }: { startups: StartupSummary[]; filtered: boolean }) {
  const avgPotential = startups.length ? startups.reduce((sum, s) => sum + s.scores.potential, 0) / startups.length : 0;
  const active = startups.filter((s) => s.pipeline_stage === "diligence" || s.pipeline_stage === "term-sheet").length;
  const disclosed = startups.reduce((sum, s) => sum + (s.total_disclosed_usd ?? 0), 0);

  return (
    <div className="mb-5 grid grid-cols-2 gap-4 xl:grid-cols-4">
      <StatCard label="Startups" value={startups.length} sub={filtered ? "Matching search" : "All tracked"} />
      <StatCard label="Avg. investment potential" value={score(avgPotential)} sub="out of 100" />
      <StatCard label="In diligence or term sheet" value={active} sub="active deals" />
      <StatCard label="Disclosed funding" value={compactMoney(disclosed)} sub="USD, approx. FX" />
    </div>
  );
}
