import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import type { AgentEntryMatch, StartupSummary } from "@/api/types";
import { useAppData } from "@/state/AppData";
import { useAsync } from "./useAsync";
import { formatSearch, isEmpty, matchesFilters, parseSearch, type SearchFilters } from "./search";
import { formatSort, isDefaultSort, parseSort, sortStartups, type Sort } from "./sort";

interface Listing {
  startups: StartupSummary[];
  /** Search matches the agent found that aren't in the database yet. */
  entries: AgentEntryMatch[];
}

/**
 * Discover state, kept in the URL so searches are shareable:
 *   q    what the user typed → POST /api/startups/search (LightRAG), most relevant first
 *   f    filters (chips, Filters panel), applied here to whatever is listed
 *   sort column and direction, e.g. -potential; also applied here
 * Without q, everything is listed via GET /api/startups. Editing filters or the sort never
 * re-runs the search.
 */
export function useDealFlowSearch() {
  const { vocabulary } = useAppData();
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const encodedFilters = params.get("f") ?? "";
  const searching = query !== "";

  const filters = useMemo(() => parseSearch(encodedFilters, vocabulary), [encodedFilters, vocabulary]);

  const listing = useAsync<Listing>(
    () =>
      searching
        ? api.searchStartups(query).then((r) => ({ startups: r.results, entries: r.entries }))
        : api.startups().then((startups) => ({ startups, entries: [] })),
    [query],
  );
  const data = listing.data;

  const sort = parseSort(params.get("sort"), searching);
  const results = useMemo(
    () =>
      sortStartups(
        (data?.startups ?? []).filter((s) => matchesFilters(s, filters)),
        sort,
      ),
    [data, filters, sort],
  );

  const updateParams = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { replace: true });
  };

  const entries = data?.entries.length ?? 0;

  return {
    query,
    results,
    filters,
    sort,
    searching,
    error: listing.error,
    hasResponse: data !== null,
    loading: listing.loading && data === null,
    /** Waiting on the backend search for a typed query. */
    interpreting: listing.loading && searching,
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
