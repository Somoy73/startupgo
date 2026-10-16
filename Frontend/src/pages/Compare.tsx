import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { DIMENSIONS, type StartupDetail } from "../api/types";
import { BandBadge } from "../components/Scores";
import { compactMoney, score } from "../lib/format";
import { useAsync } from "../lib/useAsync";

// First three categorical slots validate all-pairs in both modes (dataviz palette), so max 3.
const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];
const MAX = 3;

export function Compare() {
  const [params, setParams] = useSearchParams();
  const slugs = (params.get("s") ?? "").split(",").filter(Boolean).slice(0, MAX);
  const all = useAsync(() => api.startups({ sort: "name" }), []);
  const picked = useAsync(() => (slugs.length ? api.compare(slugs) : Promise.resolve([])), [slugs.join(",")]);

  const setSlugs = (next: string[]) => setParams(next.length ? { s: next.join(",") } : {}, { replace: true });
  const items = picked.data ?? [];

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Compare</h1>
          <p>Up to three startups side by side across readiness, ocean impact and momentum.</p>
        </div>
      </div>

      <div className="filters">
        {Array.from({ length: MAX }, (_, i) => (
          <div className="row-gap" key={i}>
            <span aria-hidden style={{ width: 10, height: 10, borderRadius: "50%", background: SERIES[i] }} />
            <label className="visually-hidden" htmlFor={`pick-${i}`}>Startup {i + 1}</label>
            <select
              id={`pick-${i}`}
              className="select"
              value={slugs[i] ?? ""}
              onChange={(e) => {
                const next = [...slugs];
                if (e.target.value) next[i] = e.target.value;
                else next.splice(i, 1);
                setSlugs(next.filter(Boolean));
              }}
            >
              <option value="">Startup {i + 1}…</option>
              {all.data
                ?.filter((s) => s.slug === slugs[i] || !slugs.includes(s.slug))
                .map((s) => (
                  <option key={s.slug} value={s.slug}>{s.name}</option>
                ))}
            </select>
          </div>
        ))}
      </div>

      {items.length === 0 ? (
        <div className="card empty">Pick at least two startups to compare.</div>
      ) : (
        <div className="stack">
          <section className="card card-pad">
            <div className="card-head">
              <h2>Readiness levels (KTH IRL)</h2>
              <Legend items={items} />
            </div>
            <DotPlot items={items} />
          </section>

          <section className="card card-pad">
            <div className="card-head"><h2>Scores</h2></div>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Metric</th>
                    {items.map((s, i) => (
                      <th key={s.slug}>
                        <span className="row-gap">
                          <span aria-hidden style={{ width: 10, height: 10, borderRadius: "50%", background: SERIES[i] }} />
                          <Link to={`/startups/${s.slug}`}>{s.name}</Link>
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <Row label="Investment potential" items={items} render={(s) => <span className="row-gap"><strong className="tabular">{score(s.scores.potential)}</strong><BandBadge band={s.scores.band} /></span>} />
                  <Row label="Readiness index" items={items} render={(s) => score(s.scores.readiness)} />
                  <Row label="Ocean impact" items={items} render={(s) => score(s.scores.ocean_impact)} />
                  <Row label="Funding momentum" items={items} render={(s) => score(s.scores.momentum)} />
                  <Row label="Imbalance penalty" items={items} render={(s) => (s.scores.imbalance_penalty ? `−${s.scores.imbalance_penalty}` : "None")} />
                  <Row label="Ocean impact areas" items={items} render={(s) => s.scores.ocean_areas_covered.join(", ") || "None"} />
                  <Row label="Best impact evidence" items={items} render={(s) => s.scores.ocean_evidence_label} />
                  <Row label="Disclosed funding" items={items} render={(s) => compactMoney(s.total_disclosed_usd)} />
                  <Row label="Sector" items={items} render={(s) => s.sector} />
                  {DIMENSIONS.map((d) => (
                    <Row key={d.key} label={`${d.code} · ${d.name}`} items={items} render={(s) => s.readiness[d.key]} />
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </>
  );
}

function Row({ label, items, render }: { label: string; items: StartupDetail[]; render: (s: StartupDetail) => React.ReactNode }) {
  return (
    <tr>
      <td className="secondary">{label}</td>
      {items.map((s) => (
        <td key={s.slug} className="tabular">{render(s)}</td>
      ))}
    </tr>
  );
}

function Legend({ items }: { items: StartupDetail[] }) {
  return (
    <div className="legend">
      {items.map((s, i) => (
        <span key={s.slug}>
          <i style={{ background: SERIES[i] }} /> {s.name}
        </span>
      ))}
    </div>
  );
}

/** One row per dimension on a shared 1-9 axis; a dot per startup, offset vertically when levels tie. */
function DotPlot({ items }: { items: StartupDetail[] }) {
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  const width = 960;
  const left = 130;
  const right = 24;
  const rowH = 44;
  const top = 28;
  const height = top + DIMENSIONS.length * rowH;
  const x = (level: number) => left + ((level - 1) / 8) * (width - left - right);

  return (
    <div style={{ position: "relative" }}>
      <svg className="dotplot" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Readiness levels by dimension for the selected startups">
        {Array.from({ length: 9 }, (_, i) => (
          <g key={i}>
            <line className="gridline" x1={x(i + 1)} x2={x(i + 1)} y1={top - 8} y2={height - 8} />
            <text x={x(i + 1)} y={14} textAnchor="middle">{i + 1}</text>
          </g>
        ))}
        {DIMENSIONS.map((d, row) => {
          const cy = top + row * rowH + rowH / 2 - 6;
          const values = items.map((s) => s.readiness[d.key]);
          return (
            <g key={d.key}>
              <text className="dim-label" x={0} y={cy - 2}>{d.code}</text>
              <text x={0} y={cy + 13}>{d.name}</text>
              <line className="range" x1={x(Math.min(...values))} x2={x(Math.max(...values))} y1={cy} y2={cy} />
              {items.map((s, i) => {
                const v = s.readiness[d.key];
                const tiesBefore = values.slice(0, i).filter((o) => o === v).length;
                const tieCount = values.filter((o) => o === v).length;
                const dy = tieCount > 1 ? (tiesBefore - (tieCount - 1) / 2) * 14 : 0;
                const label = `${s.name} · ${d.code} ${v}/9`;
                return (
                  <g key={s.slug}>
                    <circle cx={x(v)} cy={cy + dy} r={6} fill={SERIES[i]} />
                    {/* Larger invisible hit target */}
                    <circle
                      cx={x(v)}
                      cy={cy + dy}
                      r={14}
                      fill="transparent"
                      stroke="none"
                      tabIndex={0}
                      aria-label={label}
                      onMouseEnter={(e) => setTip({ x: e.clientX, y: e.clientY, text: label })}
                      onMouseMove={(e) => setTip({ x: e.clientX, y: e.clientY, text: label })}
                      onMouseLeave={() => setTip(null)}
                      onFocus={(e) => {
                        const r = (e.target as SVGCircleElement).getBoundingClientRect();
                        setTip({ x: r.left + r.width / 2, y: r.top, text: label });
                      }}
                      onBlur={() => setTip(null)}
                    />
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
      {tip && <div className="tooltip" style={{ left: tip.x, top: tip.y }}>{tip.text}</div>}
    </div>
  );
}
