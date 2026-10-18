import type { ReactNode } from "react";
import { ApiError, backend } from "../../api/backend";
import type { InvestmentMemo } from "../../api/backend-types";
import { IconBack, IconExternal } from "../../components/Icons";
import { compactMoney, PIPELINE_LABELS, stageLabel } from "../../lib/format";
import { Link, useParams } from "../../lib/navigation";
import { useAsync } from "../../lib/useAsync";

const loadMemo = (slug: string) =>
  backend.memo(slug).catch((e: unknown) => {
    if (e instanceof ApiError && e.status === 404)
      throw new Error(`No startup “${slug}” in the database.`);
    throw e;
  });

const pct = (n: number) => `${Math.round(n * 100)}%`;
const money = (amount: number | null, currency: string | null) =>
  amount == null ? "Undisclosed" : compactMoney(amount, currency ?? "USD");
const host = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
};

/** One-click investment memo: a printable brief built by GET /api/startups/{slug}/memo. "Download PDF" prints it. */
export function MemoPage() {
  const { slug = "" } = useParams();
  const { data: memo, error, loading } = useAsync(() => loadMemo(slug), [slug]);

  if (error) return <p className="empty error">{error}</p>;
  if (loading || !memo) return <p className="empty">Preparing the investment memo…</p>;

  return (
    <>
      <div className="memo-toolbar">
        <Link to={`/startups/${slug}`} className="back">
          <IconBack /> Back to profile
        </Link>
        <button type="button" className="btn btn-primary" onClick={() => window.print()}>
          Download PDF
        </button>
      </div>
      <MemoDocument memo={memo} />
    </>
  );
}

function MemoDocument({ memo }: { memo: InvestmentMemo }) {
  const { startup: s, recommendation: rec } = memo;
  const location = [s.city, s.country].filter((x, i, a) => x && a.indexOf(x) === i).join(", ");
  const rubric = s.investment;
  const kpis = s.ocean_kpis.filter((k) => k.evidence_level > 0);

  // Sections are numbered in the order they appear; empty ones are left out.
  const sections: { title: string; body: ReactNode }[] = [];
  const add = (title: string, show: boolean, body: ReactNode) =>
    show && sections.push({ title, body });

  add("Executive summary", true, <p className="memo-summary">{memo.summary.join(" ")}</p>);

  add(
    "Investment highlights and key risks",
    memo.highlights.length + memo.risks.length > 0,
    <div className="memo-columns">
      <div>
        <h4 className="memo-subhead is-positive">Highlights</h4>
        <BulletList items={memo.highlights} empty="No standout strengths on record yet." />
      </div>
      <div>
        <h4 className="memo-subhead is-caution">Risks</h4>
        <BulletList items={memo.risks} empty="No specific risks flagged." />
      </div>
    </div>,
  );

  add(
    "Readiness profile (KTH Innovation Readiness Levels)",
    s.levels.length > 0,
    <table className="memo-table">
      <thead>
        <tr>
          <th>Dimension</th>
          <th>Level</th>
          <th>Where they are</th>
          <th>Next milestone</th>
        </tr>
      </thead>
      <tbody>
        {s.levels.map((l) => (
          <tr
            key={l.dimension}
            className={s.scores.lagging_dimensions.includes(l.dimension) ? "is-lagging" : undefined}
          >
            <td>
              <strong>{l.name}</strong>
              <div className="memo-muted">{l.dimension}</div>
            </td>
            <td>
              <LevelBar level={l.level} />
            </td>
            <td>{l.summary}</td>
            <td className="memo-muted">{l.next_summary ?? "Top level reached"}</td>
          </tr>
        ))}
      </tbody>
    </table>,
  );

  add(
    "Ocean impact (Ocean Impact Navigator)",
    kpis.length > 0,
    <table className="memo-table">
      <thead>
        <tr>
          <th>KPI</th>
          <th>Impact area</th>
          <th>Evidence</th>
          <th>Claim</th>
        </tr>
      </thead>
      <tbody>
        {kpis.map((k) => (
          <tr key={k.kpi_code}>
            <td>
              <strong>{k.kpi_code}</strong> {k.kpi_name}
            </td>
            <td>{k.area_name}</td>
            <td>
              <span className={`memo-chip evidence-${k.evidence_level}`}>
                {k.evidence_level}/4 · {k.evidence_label}
              </span>
            </td>
            <td>
              {k.claim}
              {k.source_url && <SourceLink url={k.source_url} />}
            </td>
          </tr>
        ))}
      </tbody>
    </table>,
  );

  add(
    "Investment rubric",
    !!rubric && rubric.criteria.some((c) => c.score != null),
    rubric && (
      <>
        <p className="memo-muted">
          {rubric.source === "agent"
            ? "The research agent's assessment"
            : "The agent's rubric applied to the facts on record"}
          : overall {rubric.investment_score?.toFixed(1) ?? "n/a"}/5, evidence confidence{" "}
          {pct(rubric.overall_confidence)}.
        </p>
        <table className="memo-table">
          <thead>
            <tr>
              <th>Criterion</th>
              <th>Score</th>
              <th>Confidence</th>
              <th>Basis</th>
            </tr>
          </thead>
          <tbody>
            {rubric.criteria
              .filter((c) => c.score != null)
              .map((c) => (
                <tr key={c.name}>
                  <td>
                    <strong>{c.name}</strong>
                  </td>
                  <td>
                    <Dots value={c.score} max={5} />
                  </td>
                  <td className="memo-muted">
                    {c.confidence_label} ({c.fields_found}/{c.fields_total} fields)
                  </td>
                  <td>
                    {c.reasons.length ? (
                      c.reasons.join("; ")
                    ) : (
                      <span className="memo-muted">No facts</span>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
        {rubric.criteria.some((c) => c.score == null) && (
          <p className="memo-muted memo-note">
            Not scored yet (no facts on record):{" "}
            {rubric.criteria
              .filter((c) => c.score == null)
              .map((c) => c.name)
              .join(", ")}
            .
          </p>
        )}
      </>
    ),
  );

  add(
    "Team and investors",
    memo.founders.length + memo.investors.length > 0,
    <div className="memo-columns">
      <div>
        <h4 className="memo-subhead">Founders and board</h4>
        {memo.founders.length === 0 ? (
          <p className="memo-muted">No founders on record.</p>
        ) : (
          <ul className="memo-people">
            {memo.founders.map((p) => {
              const prior = p.ventures.filter((v) => v.before_startup).length;
              return (
                <li key={p.name + p.role}>
                  <strong>{p.name}</strong> <span className="memo-muted">· {p.role}</span>
                  {prior > 0 && <div className="memo-muted">{prior} prior venture(s)</div>}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div>
        <h4 className="memo-subhead">Investors</h4>
        {memo.investors.length === 0 ? (
          <p className="memo-muted">No investors on record.</p>
        ) : (
          <ul className="memo-people">
            {memo.investors.map((i) => (
              <li key={i.name}>
                <strong>{i.name}</strong> <span className="memo-muted">· {i.role}</span>
                {i.kind && <div className="memo-muted">{i.kind.replaceAll("-", " ")}</div>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>,
  );

  add(
    "Funding history",
    memo.funding.length > 0,
    <table className="memo-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Event</th>
          <th className="num">Amount</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        {memo.funding.map((f, i) => (
          <tr key={i}>
            <td className="tabular">{f.event_date ?? "—"}</td>
            <td>
              {f.round_label
                ? stageLabel(f.round_label)
                : stageLabel(f.event_type.replaceAll("_", " "))}
              <div className="memo-muted">{f.status}</div>
            </td>
            <td className="num">{money(f.amount, f.currency)}</td>
            <td className="memo-muted">
              {f.source_name.replaceAll("_", " ")}
              {f.source_url && <SourceLink url={f.source_url} />}
            </td>
          </tr>
        ))}
      </tbody>
    </table>,
  );

  add(
    "Intellectual property and public funding",
    memo.patents.length + memo.grants.length > 0,
    <div className="memo-columns">
      <div>
        <h4 className="memo-subhead">Patents ({memo.patents.length})</h4>
        {memo.patents.length === 0 ? (
          <p className="memo-muted">No patents on record.</p>
        ) : (
          <ul className="memo-people">
            {memo.patents.map((p) => (
              <li key={p.publication_number}>
                <strong>{p.publication_number}</strong>{" "}
                <span className={`memo-chip ${p.granted ? "evidence-3" : ""}`}>
                  {p.granted ? "Granted" : (p.legal_status ?? "Filed")}
                </span>
                <div className="memo-muted">{p.title}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h4 className="memo-subhead">EU grants ({memo.grants.length})</h4>
        {memo.grants.length === 0 ? (
          <p className="memo-muted">No EU-funded projects on record.</p>
        ) : (
          <ul className="memo-people">
            {memo.grants.map((g) => (
              <li key={g.project_id}>
                <strong>{g.programme ?? g.project_id}</strong>
                {g.is_eic && <span className="memo-chip evidence-3">EIC</span>}
                {g.is_mission_ocean && <span className="memo-chip evidence-2">Mission Ocean</span>}
                <div className="memo-muted">
                  {[
                    g.role,
                    g.start_date?.slice(0, 4),
                    g.ec_contribution != null && money(g.ec_contribution, g.currency ?? "EUR"),
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>,
  );

  add(
    "Comparable companies",
    memo.peers.length > 0,
    <table className="memo-table">
      <thead>
        <tr>
          <th>Company</th>
          <th>Sector</th>
          <th className="num">Similarity</th>
        </tr>
      </thead>
      <tbody>
        {memo.peers.map((p) => (
          <tr key={p.name}>
            <td>
              {p.slug ? (
                <Link to={`/startups/${p.slug}`} className="memo-peer-link">
                  <strong>{p.name}</strong>
                </Link>
              ) : (
                <strong>{p.name}</strong>
              )}
            </td>
            <td>{p.sector ?? "—"}</td>
            <td className="num">{pct(p.similarity)}</td>
          </tr>
        ))}
      </tbody>
    </table>,
  );

  add(
    "Due diligence: questions and next steps",
    memo.questions.length + memo.next_steps.length > 0,
    <div className="memo-columns">
      <div>
        <h4 className="memo-subhead">Questions for the first call</h4>
        {memo.questions.length === 0 ? (
          <p className="memo-muted">No open data gaps recorded.</p>
        ) : (
          <ol className="memo-list">
            {memo.questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ol>
        )}
      </div>
      <div>
        <h4 className="memo-subhead">Recommended next steps</h4>
        <ol className="memo-list">
          {memo.next_steps.map((n, i) => (
            <li key={i}>
              <strong>{n.action}</strong>
              {n.reason && <>: {n.reason}</>}
              {n.resource && <div className="memo-muted">{n.resource}</div>}
            </li>
          ))}
        </ol>
      </div>
    </div>,
  );

  return (
    <article className="memo-doc stagger">
      <header className="memo-cover">
        <div className="memo-brandline">
          <span>Startup Go · Investment memo</span>
          <span>Confidential</span>
        </div>
        <h1>{s.name}</h1>
        <p className="memo-tagline">{s.tagline}</p>
        <dl className="memo-facts">
          <Fact label="Sector" value={s.sector} />
          <Fact label="Location" value={location || "—"} />
          <Fact label="Stage" value={stageLabel(s.stage)} />
          <Fact label="Founded" value={s.founded_year ? String(s.founded_year) : "—"} />
          <Fact
            label="Pipeline"
            value={
              PIPELINE_LABELS[s.pipeline_stage as keyof typeof PIPELINE_LABELS] ?? s.pipeline_stage
            }
          />
          <Fact
            label="Website"
            value={
              s.website ? (
                <a href={s.website} target="_blank" rel="noreferrer">
                  {host(s.website)}
                </a>
              ) : (
                "—"
              )
            }
          />
        </dl>
      </header>

      <section className={`memo-verdict is-${rec.tone}`}>
        <div>
          <span className="memo-eyebrow">Recommendation</span>
          <strong className="memo-verdict-title">{rec.verdict}</strong>
        </div>
        <ul className="memo-verdict-points">
          {rec.points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </section>

      {s.assessed && (
        <div className="memo-metrics">
          <Metric
            label="Investment potential"
            value={Math.round(s.scores.potential)}
            suffix="/100"
            note={s.scores.band}
          />
          <Metric label="Readiness index" value={Math.round(s.scores.readiness)} suffix="/100" />
          <Metric
            label="Ocean impact"
            value={Math.round(s.scores.ocean_impact)}
            suffix="/100"
            note={s.scores.ocean_evidence_label}
          />
          <Metric label="Funding momentum" value={Math.round(s.scores.momentum)} suffix="/100" />
          <Metric
            label="Disclosed funding"
            value={s.total_disclosed_usd ? compactMoney(s.total_disclosed_usd) : "—"}
            note={s.last_round_on ? `Last round ${s.last_round_on}` : undefined}
          />
        </div>
      )}

      {sections.map((sec, i) => (
        <section key={sec.title} className="memo-section">
          <h2>
            <span className="memo-num">{String(i + 1).padStart(2, "0")}</span>
            {sec.title}
          </h2>
          {sec.body}
        </section>
      ))}

      <footer className="memo-footer">
        {s.sources.length > 0 && (
          <>
            <h4 className="memo-subhead">Sources</h4>
            <ol className="memo-sources">
              {s.sources.map((src) => (
                <li key={src.url}>
                  {src.title} <span className="memo-muted">({host(src.url)})</span>
                </li>
              ))}
            </ol>
          </>
        )}
        <p>Generated by StartupGo on {memo.generated_at}.</p>
      </footer>
    </article>
  );
}

function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function Metric({
  label,
  value,
  suffix,
  note,
}: {
  label: string;
  value: ReactNode;
  suffix?: string | undefined;
  note?: string | undefined;
}) {
  return (
    <div className="memo-metric">
      <span className="memo-eyebrow">{label}</span>
      <strong>
        {value}
        {suffix && <small>{suffix}</small>}
      </strong>
      {note && <span className="memo-muted">{note}</span>}
    </div>
  );
}

function LevelBar({ level }: { level: number }) {
  return (
    <div className="memo-level" aria-label={`Level ${level} of 9`}>
      <span className="memo-level-num">{level}</span>
      <span className="memo-level-bar" aria-hidden>
        {Array.from({ length: 9 }, (_, i) => (
          <i key={i} className={i < level ? "is-on" : undefined} />
        ))}
      </span>
    </div>
  );
}

function Dots({ value, max }: { value: number | null; max: number }) {
  if (value == null) return <span className="memo-muted">n/a</span>;
  return (
    <span className="memo-dots" aria-label={`${value} of ${max}`}>
      {Array.from({ length: max }, (_, i) => (
        <i key={i} className={i < value ? "is-on" : undefined} />
      ))}
      <b>{value}/5</b>
    </span>
  );
}

function BulletList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <p className="memo-muted">{empty}</p>;
  return (
    <ul className="memo-bullets">
      {items.map((t) => (
        <li key={t}>{t}</li>
      ))}
    </ul>
  );
}

function SourceLink({ url }: { url: string }) {
  return (
    <>
      {" "}
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        className="memo-src"
        aria-label={`Source: ${host(url)}`}
      >
        <IconExternal />
      </a>
    </>
  );
}
