import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { StartupQuery } from "../api/types";
import { IconSearch } from "../components/Icons";
import { BandBadge, LevelPill, Meter } from "../components/Scores";
import { compactMoney, PIPELINE_LABELS, score, titleCase } from "../lib/format";
import { useAsync } from "../lib/useAsync";

const FILTER_KEYS: (keyof StartupQuery)[] = ["q", "sector", "country", "stage", "impact_area", "min_trl", "min_brl", "sort"];

export function DealFlow() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string[]>([]);
  const [search, setSearch] = useState(params.get("q") ?? "");

  const query: StartupQuery = useMemo(
    () => Object.fromEntries(FILTER_KEYS.map((k) => [k, params.get(k) ?? undefined])),
    [params],
  );
  const startups = useAsync(() => api.startups(query), [JSON.stringify(query)]);
  const filters = useAsync(() => api.filters(), []);

  const setFilter = (key: keyof StartupQuery, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const toggle = (slug: string) =>
    setSelected((s) => (s.includes(slug) ? s.filter((x) => x !== slug) : s.length >= 3 ? s : [...s, slug]));

  const list = startups.data ?? [];
  const avgPotential = list.length ? list.reduce((a, s) => a + s.scores.potential, 0) / list.length : 0;
  const inDiligence = list.filter((s) => ["diligence", "term-sheet"].includes(s.pipeline_stage)).length;
  const disclosed = list.reduce((a, s) => a + (s.total_disclosed_usd ?? 0), 0);
  const hasFilters = FILTER_KEYS.some((k) => k !== "sort" && params.get(k));

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Deal flow</h1>
          <p>Ocean & deep-tech startups ranked by Investment Potential: readiness, ocean impact and funding momentum.</p>
        </div>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        <div className="card stat">
          <span className="label">Startups in view</span>
          <span className="value">{list.length}</span>
          <span className="sub">{hasFilters ? "Filtered" : "All tracked"}</span>
        </div>
        <div className="card stat">
          <span className="label">Avg. investment potential</span>
          <span className="value">{score(avgPotential)}</span>
          <span className="sub">out of 100</span>
        </div>
        <div className="card stat">
          <span className="label">In diligence or term sheet</span>
          <span className="value">{inDiligence}</span>
          <span className="sub">active deals</span>
        </div>
        <div className="card stat">
          <span className="label">Disclosed funding</span>
          <span className="value">{compactMoney(disclosed)}</span>
          <span className="sub">USD, approx. FX</span>
        </div>
      </div>

      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          setFilter("q", search.trim());
        }}
      >
        <div className="search">
          <IconSearch />
          <label className="visually-hidden" htmlFor="q">Search startups</label>
          <input
            id="q"
            className="input"
            placeholder="Search: kelp, Namibia, carbon capture…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onBlur={() => setFilter("q", search.trim())}
          />
        </div>
        <Select label="Sector" value={query.sector} options={filters.data?.sectors} onChange={(v) => setFilter("sector", v)} />
        <Select label="Country" value={query.country} options={filters.data?.countries} onChange={(v) => setFilter("country", v)} />
        <Select label="Stage" value={query.stage} options={filters.data?.stages} format={titleCase} onChange={(v) => setFilter("stage", v)} />
        <Select
          label="Ocean impact area"
          value={query.impact_area}
          options={filters.data?.impact_areas.map((a) => a.code)}
          format={(c) => `${c} · ${filters.data?.impact_areas.find((a) => a.code === c)?.name ?? ""}`}
          onChange={(v) => setFilter("impact_area", v)}
        />
        <Select label="Min TRL" value={query.min_trl} options={LEVELS} format={(l) => `TRL ≥ ${l}`} onChange={(v) => setFilter("min_trl", v)} />
        <Select label="Min BRL" value={query.min_brl} options={LEVELS} format={(l) => `BRL ≥ ${l}`} onChange={(v) => setFilter("min_brl", v)} />
        <label className="visually-hidden" htmlFor="sort">Sort by</label>
        <select id="sort" className="select" value={query.sort ?? "potential"} onChange={(e) => setFilter("sort", e.target.value)}>
          <option value="potential">Sort: Investment potential</option>
          <option value="readiness">Sort: Readiness</option>
          <option value="ocean">Sort: Ocean impact</option>
          <option value="momentum">Sort: Momentum</option>
          <option value="trl">Sort: TRL</option>
          <option value="brl">Sort: BRL</option>
          <option value="name">Sort: Name</option>
        </select>
        {hasFilters && (
          <button
            type="button"
            className="btn"
            onClick={() => {
              setSearch("");
              setParams(new URLSearchParams(), { replace: true });
            }}
          >
            Clear
          </button>
        )}
      </form>

      <div className="card">
        {startups.error && <p className="empty error">Couldn't load startups: {startups.error}. Is the backend running on :8000?</p>}
        {!startups.error && !startups.loading && list.length === 0 && <p className="empty">No startups match these filters.</p>}
        {list.length > 0 && (
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
                {list.map((s) => (
                  <tr key={s.slug} className="clickable" onClick={() => navigate(`/startups/${s.slug}`)}>
                    <td onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        aria-label={`Compare ${s.name}`}
                        checked={selected.includes(s.slug)}
                        disabled={!selected.includes(s.slug) && selected.length >= 3}
                        onChange={() => toggle(s.slug)}
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
                    <td className="num" data-label="TRL"><LevelPill level={s.readiness.trl} label="TRL" /></td>
                    <td className="num" data-label="BRL"><LevelPill level={s.readiness.brl} label="BRL" /></td>
                    <td data-label="Ocean impact"><Meter value={s.scores.ocean_impact} label="Ocean impact" /></td>
                    <td data-label="Investment potential">
                      <div className="row-gap">
                        <Meter value={s.scores.potential} label="Investment potential" />
                        <BandBadge band={s.scores.band} />
                      </div>
                    </td>
                    <td data-label="Pipeline"><span className="chip">{PIPELINE_LABELS[s.pipeline_stage]}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <p className="small muted" style={{ marginTop: 10 }}>
        Readiness levels are low-confidence seed estimates from public sources. Validate them in diligence.
      </p>

      {selected.length > 0 && (
        <div className="tray" role="region" aria-label="Comparison selection">
          <span className="small">{selected.length} of 3 selected</span>
          <button className="btn" onClick={() => setSelected([])}>Clear</button>
          <button className="btn" disabled={selected.length < 2} onClick={() => navigate(`/compare?s=${selected.join(",")}`)}>
            Compare
          </button>
        </div>
      )}
    </>
  );
}

const LEVELS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];

function Select({
  label,
  value,
  options,
  format = (v) => v,
  onChange,
}: {
  label: string;
  value?: string;
  options?: string[];
  format?: (v: string) => string;
  onChange: (v: string) => void;
}) {
  const id = `f-${label.replace(/\W+/g, "-").toLowerCase()}`;
  return (
    <>
      <label className="visually-hidden" htmlFor={id}>{label}</label>
      <select id={id} className="select" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
        <option value="">{label}: All</option>
        {options?.map((o) => (
          <option key={o} value={o}>{format(o)}</option>
        ))}
      </select>
    </>
  );
}
