import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { AgentEntryMatch, StartupSummary } from "../api/types";
import { useAppData } from "../state/AppData";
import { useSearchParams } from "./navigation";
import { formatSearch, isEmpty, matchesFilters, parseSearch, type SearchFilters } from "./search";
import { formatSort, isDefaultSort, parseSort, sortStartups, type Sort } from "./sort";

type SearchState = {
  query: string;
  startups: StartupSummary[];
  /** Matches the discovery agent found that aren't in the database yet. */
  entries: AgentEntryMatch[];
  error: string | null;
};

/**
 * Discover state, kept in the URL so searches are shareable:
 *   q    what the user typed → api.searchStartups, most relevant first
 *   f    filters (chips, Filters panel), applied here to whatever is listed
 *   sort column and direction, e.g. -potential; also applied here
 * Without q, every startup is listed (from AppData). Editing filters or the sort never
 * re-runs the search.
 */
export function useDiscoverSearch() {
  const { startups, loading: listLoading, error: listError } = useAppData();
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const encodedFilters = params.get("f") ?? "";
  const searching = query !== "";

  const [search, setSearch] = useState<SearchState | null>(null);
  useEffect(() => {
    if (!searching) return;
    let cancelled = false;
    api
      .searchStartups(query)
      .then((r) => !cancelled && setSearch({ query, startups: r.results, entries: r.entries, error: null }))
      .catch((e: Error) => !cancelled && setSearch({ query, startups: [], entries: [], error: e.message }));
    return () => {
      cancelled = true;
    };
  }, [query, searching]);

  // A result for an older query is stale while the new one is on its way.
  const current = searching && search?.query === query ? search : null;
  const listed = useMemo(() => (searching ? (current?.startups ?? []) : startups), [searching, current, startups]);
  const loading = searching ? current === null : listLoading;
  const error = searching ? (current?.error ?? null) : listError;

  const filters = useMemo(() => parseSearch(encodedFilters), [encodedFilters]);
  const sortParam = params.get("sort");
  const sort = useMemo(() => parseSort(sortParam, searching), [sortParam, searching]);
  const results = useMemo(
    () =>
      sortStartups(
        listed.filter((s) => matchesFilters(s, filters)),
        sort,
      ),
    [listed, filters, sort],
  );

  const updateParams = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { replace: true });
  };

  const entries = current?.entries.length ?? 0;

  return {
    query,
    results,
    filters,
    sort,
    searching,
    error,
    loading,
    hasResponse: !loading && error === null,
    notice:
      entries > 0
        ? `${entries} more match${entries === 1 ? "" : "es"} from the discovery agent ${entries === 1 ? "isn't" : "aren't"} in your database yet.`
        : null,

    submitQuery: (q: string) => updateParams({ q }),
    setFilters: (f: SearchFilters) => updateParams({ f: isEmpty(f) ? null : formatSearch(f) }),
    clear: () => updateParams({ q: null, f: null }),
    setSort: (next: Sort) => updateParams({ sort: isDefaultSort(next, searching) ? null : formatSort(next) }),
  };
}
