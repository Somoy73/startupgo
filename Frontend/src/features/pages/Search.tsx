import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getRouteApi, useNavigate } from "@tanstack/react-router";
import { backend } from "../../api/backend";
import { DiscoverSearchBar } from "../../components/DiscoverSearchBar";
import { ColumnPicker, COLUMNS, DEFAULT_COLUMNS, StartupTable } from "../../components/StartupTable";
import { Button } from "../../components/ui/button";
import { filterStartups, frameworksOptions, parseFilters, parseSearchSort, sortSearchResults, startupListOptions, type SearchFilters, type SearchSortKey } from "../../lib/discover-search";
const searchRoute = getRouteApi("/search");

export function Search() {
  const params = searchRoute.useSearch();
  const navigate = useNavigate();
  const query = params.q;
  const type = params.type;
  const euProjects = type === "eu-projects";
  const filters = parseFilters(params.filters);
  const list = useQuery(startupListOptions);
  useQuery(frameworksOptions); // for the filter panel's impact areas
  // LightRAG is slow and costs a model call: keep results for the session, and don't retry failures.
  const response = useQuery({ queryKey: ["discover", "search", query], queryFn: () => backend.search(query), enabled: !!query && !euProjects, staleTime: Infinity, retry: false });
  const sort = parseSearchSort(params.sort, query);
  const [columns, setColumns] = useState(DEFAULT_COLUMNS);
  const [storageReady, setStorageReady] = useState(false);
  useEffect(() => {
    try {
      const stored: unknown = JSON.parse(localStorage.getItem("discover.columns") ?? "null");
      if (Array.isArray(stored)) setColumns(stored.filter((id): id is string => typeof id === "string" && COLUMNS.some((c) => c.id === id)));
    } catch { /* Storage can be unavailable in private browsers. */ }
    setStorageReady(true);
  }, []);
  useEffect(() => {
    if (storageReady) { try { localStorage.setItem("discover.columns", JSON.stringify(columns)); } catch { /* Keep session choices. */ } }
  }, [columns, storageReady]);
  const update = (patch: Partial<typeof params>) => navigate({ to: "/search", search: (previous) => ({
    q: patch.q ?? previous["q"] ?? "",
    type: patch.type ?? (previous["type"] === "eu-projects" ? "eu-projects" : "startups"),
    filters: patch.filters ?? previous["filters"] ?? "",
    sort: patch.sort ?? previous["sort"] ?? "",
  }), resetScroll: false });
  const clear = () => { void update({ q: "", filters: "", sort: "" }); };
  const setFilters = (next: SearchFilters) => { void update({ filters: JSON.stringify(next) }); };
  const items = (query ? response.data?.results : list.data) ?? [];
  const results = sortSearchResults(filterStartups(items, filters), sort);
  const busy = !euProjects && (query ? response.isPending : list.isPending);
  const error = query ? response.error : list.error;
  const retry = () => { void (query ? response.refetch() : list.refetch()); };
  const onSort = (key: SearchSortKey) => { const direction = sort.key === key ? sort.direction === "asc" ? "desc" : "asc" : key === "name" || key === "stage" || key === "pipeline" ? "asc" : "desc"; void update({ sort: `${key}:${direction}` }); };
  return <>
    <div className="page-head"><div><h1>Search</h1><p>Discover startups and EU projects in the blue economy.</p></div></div>
    <DiscoverSearchBar query={query} filters={filters} type={type} busy={busy} onSearch={(q) => { void update({ q, sort: "" }); }} onFiltersChange={setFilters} onTypeChange={(next) => { void update({ type: next }); }} onClear={clear} />
    {euProjects ? <div className="card discover-results" aria-live="polite"><p className="empty">List of EU projects. Not implemented</p></div> : <div className="card discover-results" aria-live="polite">
      {busy ? <p className="empty">{query ? "Searching…" : "Loading startups…"}</p> : error ? <div className="empty" role="alert"><p className="error">{query ? "Search failed" : "Couldn’t load startups"}: {error.message}</p><Button className="mt-3" variant="outline" onClick={retry}>Try again</Button></div> : <>
        <div className="discover-results-head"><span className="small muted tabular">{results.length} startup{results.length === 1 ? "" : "s"}{query && sort.key === "relevance" ? " · Most relevant first" : ""}</span><ColumnPicker columns={columns} onChange={setColumns} /></div>
        {results.length ? <StartupTable startups={results} columns={columns} sort={sort} onSort={onSort} onOpen={(slug) => { void navigate({ to: "/startups/$slug", params: { slug } }); }} /> : <div className="empty"><p>No startups match this search.</p><Button variant="outline" className="mt-3" onClick={clear}>Clear search</Button></div>}
        {response.data && response.data.entries.length > 0 && <p className="notice">{response.data.entries.length} agent discoveries are not yet available as startup profiles.</p>}
      </>}
    </div>}
    {!euProjects && <p className="discover-footnote small">Readiness levels are low-confidence public-source estimates.</p>}
  </>;
}
