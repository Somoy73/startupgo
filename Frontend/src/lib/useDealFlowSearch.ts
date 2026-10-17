import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/api/client";
import type { SearchRequest, SearchResponse } from "@/api/types";
import { useAsync } from "./useAsync";
import {
  emptyFilters,
  formatSearch,
  fromApiFilters,
  isEmpty,
  parseSearch,
  toApiFilters,
  type SearchFilters,
  type Vocabulary,
} from "./search";
import { formatSort, isDefaultSort, parseSort, sortStartups, type Sort } from "./sort";

// The `f` parameter is written by formatSearch in key:value form, so it decodes without the data vocabulary.
const NO_VOCABULARY: Vocabulary = { sectors: [], countries: [] };

/**
 * Deal-flow search state, kept in the URL so searches are shareable:
 *   q    what the user typed               → POST /api/search { query }
 *   f    filters after editing chips/menus → POST /api/search { filters }
 *   sort column and direction, e.g. -potential (applied here, so changing it never re-runs the search)
 * With neither q nor f, everything is listed via GET /api/startups.
 */
export function useDealFlowSearch() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const editedFilters = params.get("f");

  const sentFilters = useMemo(
    () => (editedFilters !== null ? parseSearch(editedFilters, NO_VOCABULARY) : null),
    [editedFilters],
  );
  const request: SearchRequest | null = useMemo(() => {
    if (sentFilters) return { filters: toApiFilters(sentFilters) };
    if (query) return { query };
    return null;
  }, [query, sentFilters]);

  const search = useAsync<SearchResponse>(
    () =>
      request
        ? api.search(request)
        : api.startups().then((startups) => ({ query: null, filters: null, notice: null, startups })),
    [request],
  );
  const response = search.data;

  const searching = request !== null;
  const sort = parseSort(params.get("sort"), searching);
  const results = useMemo(() => sortStartups(response?.startups ?? [], sort), [response, sort]);
  // Chips: what the search says it applied, else what we sent.
  const filters = response?.filters ? fromApiFilters(response.filters) : sentFilters;

  const updateParams = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { replace: true });
  };

  return {
    query,
    results,
    filters,
    /** `filters`, or empty ones: what the dropdowns show and edit. */
    current: filters ?? emptyFilters(),
    sort,
    searching,
    error: search.error,
    hasResponse: response !== null,
    loading: search.loading && response === null,
    /** Waiting on a typed query (not a filter edit). */
    interpreting: search.loading && request !== null && "query" in request,
    /** The chips are the search's reading of `query`, not edited filters. */
    interpreted: editedFilters === null && Boolean(response?.filters),
    notice: editedFilters === null ? (response?.notice ?? null) : null,

    submitQuery: (q: string) => updateParams({ q, f: null }),
    // Edited filters keep `q` for context but take precedence over it.
    setFilters: (f: SearchFilters) =>
      isEmpty(f) ? updateParams({ q: null, f: null }) : updateParams({ f: formatSearch(f) }),
    clear: () => updateParams({ q: null, f: null }),
    setSort: (next: Sort) => updateParams({ sort: isDefaultSort(next, searching) ? null : formatSort(next) }),
  };
}
