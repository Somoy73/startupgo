import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { SearchRequest, SearchResponse, StartupSummary } from "../api/types";
import { FilterSelect } from "../components/Controls";
import { BandBadge, LevelPill, Meter } from "../components/Scores";
import { SearchBar } from "../components/SearchBar";
import { compactMoney, PIPELINE_LABELS, score } from "../lib/format";
import { REGIONS } from "../lib/regions";
import {
  emptyFilters,
  formatSearch,
  fromApiFilters,
  isEmpty,
  parseSearch,
  toApiFilters,
  type SearchFilters,
  type Vocabulary,
} from "../lib/search";
import { effectiveSort, SORTS, sortStartups } from "../lib/sort";
import { useAsync } from "../lib/useAsync";
import { useAppData } from "../state/AppData";

const MAX_COMPARE = 3;

// The `f` parameter is written by formatSearch in key:value form, so it decodes without the data vocabulary.
const NO_VOCABULARY: Vocabulary = { sectors: [], countries: [] };

export function DealFlow() {
  const { vocabulary, frameworks } = useAppData();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string[]>([]);

  // URL: `q` = what the user typed; `f` = filters after the user edited chips or dropdowns.
  // Both go to POST /api/search; with neither, the page lists everything via GET /api/startups.
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
  // Sorted here so changing the order never re-runs the search.
  const sort = effectiveSort(params.get("sort"), request !== null);
  const results = useMemo(() => sortStartups(response?.startups ?? [], sort), [response, sort]);
  // Chips: what the search says it applied, else what we sent.
  const filters = response?.filters ? fromApiFilters(response.filters) : sentFilters;
  const loading = search.loading && !response;

  const updateParams = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { replace: true });
  };
  const setParam = (key: string, value: string) => updateParams({ [key]: value });
  // Edited filters keep `q` for context but take precedence over it.
  const setFilters = (f: SearchFilters) =>
    isEmpty(f) ? updateParams({ q: null, f: null }) : updateParams({ f: formatSearch(f) });
  const current = filters ?? emptyFilters();

  const toggleCompare = (slug: string) =>
    setSelected((s) => (s.includes(slug) ? s.filter((x) => x !== slug) : s.length < MAX_COMPARE ? [...s, slug] : s));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Deal flow</h1>
          <p>Search ocean & deep-tech startups and rank them by readiness, ocean impact and funding momentum.</p>
        </div>
        <Link to="/assess" className="btn btn-primary">
          Assess a startup
        </Link>
      </div>

      <Stats startups={results} filtered={!isEmpty(current)} />

      <SearchBar
        query={query}
        filters={filters}
        interpreted={editedFilters === null && Boolean(response?.filters)}
        interpreting={search.loading && request !== null && "query" in request}
        notice={editedFilters === null ? (response?.notice ?? null) : null}
        onSearch={(q) => updateParams({ q, f: null })}
        onFiltersChange={setFilters}
        onClear={() => updateParams({ q: null, f: null })}
      />

      <div className="filters">
        <FilterSelect
          label="Sector"
          value={current.sectors[0] ?? ""}
          options={vocabulary.sectors.map((v) => ({ value: v, label: v }))}
          onChange={(v) => setFilters({ ...current, sectors: v ? [v] : [] })}
        />
        <FilterSelect
          label="Region"
          value={current.regions[0] ?? ""}
          options={REGIONS.map((r) => ({ value: r.id, label: r.label }))}
          onChange={(v) => setFilters({ ...current, regions: v ? [v as SearchFilters["regions"][number]] : [] })}
        />
        <FilterSelect
          label="Impact area"
          value={current.impactAreas[0] ?? ""}
          options={(frameworks?.ocean_impact_areas ?? []).map((a) => ({
            value: a.code,
            label: `${a.code} · ${a.name}`,
          }))}
          onChange={(v) => setFilters({ ...current, impactAreas: v ? [v] : [] })}
        />
        <label className="visually-hidden" htmlFor="sort">
          Sort by
        </label>
        <select id="sort" className="select" value={sort} onChange={(e) => setParam("sort", e.target.value)}>
          {Object.entries(SORTS)
            .filter(([key]) => key !== "relevance" || request !== null)
            .map(([key, { label }]) => (
              <option key={key} value={key}>
                Sort: {label}
              </option>
            ))}
        </select>
      </div>

      <div className="card">
        {search.error && (
          <p className="empty error">
            {request ? "Search failed" : "Couldn't load startups"}: {search.error}
          </p>
        )}
        {!search.error && loading && <p className="empty">Loading…</p>}
        {!search.error && response && results.length === 0 && (
          <div className="empty">
            <p>No startups match this search.</p>
            <button className="btn" style={{ marginTop: 12 }} onClick={() => updateParams({ q: null, f: null })}>
              Clear search
            </button>
          </div>
        )}
        {results.length > 0 && (
          <ResultsTable
            startups={results}
            selected={selected}
            onToggle={toggleCompare}
            onOpen={(slug) => navigate(`/startups/${slug}`)}
          />
        )}
      </div>
      <p className="small muted" style={{ marginTop: 10 }}>
        Seed data readiness levels are low-confidence estimates from public sources. Use Assess to record your own.
      </p>

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

function Stats({ startups, filtered }: { startups: StartupSummary[]; filtered: boolean }) {
  const avgPotential = startups.length ? startups.reduce((sum, s) => sum + s.scores.potential, 0) / startups.length : 0;
  const active = startups.filter((s) => s.pipeline_stage === "diligence" || s.pipeline_stage === "term-sheet").length;
  const disclosed = startups.reduce((sum, s) => sum + (s.total_disclosed_usd ?? 0), 0);

  return (
    <div className="grid grid-4" style={{ marginBottom: 20 }}>
      <div className="card stat">
        <span className="label">Startups</span>
        <span className="value">{startups.length}</span>
        <span className="sub">{filtered ? "Matching search" : "All tracked"}</span>
      </div>
      <div className="card stat">
        <span className="label">Avg. investment potential</span>
        <span className="value">{score(avgPotential)}</span>
        <span className="sub">out of 100</span>
      </div>
      <div className="card stat">
        <span className="label">In diligence or term sheet</span>
        <span className="value">{active}</span>
        <span className="sub">active deals</span>
      </div>
      <div className="card stat">
        <span className="label">Disclosed funding</span>
        <span className="value">{compactMoney(disclosed)}</span>
        <span className="sub">USD, approx. FX</span>
      </div>
    </div>
  );
}

function ResultsTable({
  startups,
  selected,
  onToggle,
  onOpen,
}: {
  startups: StartupSummary[];
  selected: string[];
  onToggle: (slug: string) => void;
  onOpen: (slug: string) => void;
}) {
  return (
    <div className="table-wrap">
      <table className="data responsive">
        <thead>
          <tr>
            <th aria-label="Select for comparison" />
            <th>Startup</th>
            <th>Sector · Country</th>
            <th className="num">TRL</th>
            <th className="num">BRL</th>
            <th>Ocean impact</th>
            <th>Investment potential</th>
            <th>Pipeline</th>
          </tr>
        </thead>
        <tbody>
          {startups.map((s) => (
            <tr key={s.slug} className="clickable" onClick={() => onOpen(s.slug)}>
              <td onClick={(e) => e.stopPropagation()}>
                <input
                  type="checkbox"
                  aria-label={`Compare ${s.name}`}
                  checked={selected.includes(s.slug)}
                  disabled={!selected.includes(s.slug) && selected.length >= MAX_COMPARE}
                  onChange={() => onToggle(s.slug)}
                />
              </td>
              <td className="name-cell full">
                <Link to={`/startups/${s.slug}`} onClick={(e) => e.stopPropagation()}>
                  <strong>{s.name}</strong>
                </Link>
                <span>{s.tagline}</span>
              </td>
              <td className="full secondary small">
                {s.sector} · {s.country}
              </td>
              <td className="num" data-label="TRL">
                <LevelPill level={s.readiness.trl} label="TRL" />
              </td>
              <td className="num" data-label="BRL">
                <LevelPill level={s.readiness.brl} label="BRL" />
              </td>
              <td data-label="Ocean impact">
                <Meter value={s.scores.ocean_impact} label="Ocean impact" />
              </td>
              <td data-label="Investment potential">
                <div className="row-gap">
                  <Meter value={s.scores.potential} label="Investment potential" />
                  <BandBadge band={s.scores.band} />
                </div>
              </td>
              <td data-label="Pipeline">
                <span className="chip">{PIPELINE_LABELS[s.pipeline_stage]}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
