import { Button } from "../../components/ui/button";
import { useState } from "react";
import { Link, useParams } from "../../lib/navigation";
import { api } from "../../api/client";
import { PIPELINE_STAGES, type PipelineStage } from "../../api/types";
import { IconAlert, IconBack, IconExternal } from "../../components/Icons";
import { OceanImpact } from "../../components/OceanImpact";
import { ReadinessProfile } from "../../components/ReadinessProfile";
import { BandBadge, Meter } from "../../components/Scores";
import { compactMoney, partialDate, PIPELINE_LABELS, score, stageLabel } from "../../lib/format";
import { useAsync } from "../../lib/useAsync";
import { useAppData } from "../../state/AppData";

export function StartupPage() {
  const { slug = "" } = useParams();
  const { upsertStartup } = useAppData();
  const { data: s, error, loading, setData } = useAsync(() => api.startup(slug), [slug]);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (error) return <p className="empty error">{error}</p>;
  if (loading || !s) return <p className="empty">Loading…</p>;

  const changeStage = async (stage: PipelineStage) => {
    setActionError(null);
    try {
      upsertStartup(await api.setPipeline(s.slug, stage));
      setData({ ...s, pipeline_stage: stage });
    } catch (e) {
      setActionError((e as Error).message);
    }
  };

  const submitNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!note.trim()) return;
    setSaving(true);
    setActionError(null);
    try {
      const created = await api.addNote(s.slug, note.trim());
      setData({ ...s, notes: [created, ...s.notes] });
      setNote("");
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const { scores, readiness } = s;

  return (
    <>
      <Link to="/" className="back">
        <IconBack /> Back
      </Link>
      <div className="page-head">
        <div>
          <div className="row-gap" style={{ marginBottom: 6 }}>
            <h1>{s.name}</h1>
            <BandBadge band={scores.band} />
          </div>
          <p>{s.tagline}</p>
          <p className="small muted" style={{ marginTop: 6 }}>
            {s.sector} ·{" "}
            {[s.city, s.country].filter((x, i, a) => x && a.indexOf(x) === i).join(", ")}
            {s.founded_year && ` · Founded ${s.founded_year}`} · {stageLabel(s.stage)}
            {s.website && (
              <>
                {" · "}
                <a href={s.website} target="_blank" rel="noreferrer">
                  Website <IconExternal />
                </a>
              </>
            )}
          </p>
        </div>
        <div className="row-gap" style={{ alignItems: "flex-end" }}>
          <Link to={`/assess/${s.slug}`} className="btn">
            Re-assess
          </Link>
          <div className="field">
            <label htmlFor="stage">Pipeline stage</label>
            <select
              id="stage"
              className="select"
              value={s.pipeline_stage}
              onChange={(e) => changeStage(e.target.value as PipelineStage)}
            >
              {PIPELINE_STAGES.map((p) => (
                <option key={p} value={p}>
                  {PIPELINE_LABELS[p]}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {actionError && (
        <p className="error small" style={{ marginBottom: 12 }}>
          {actionError}
        </p>
      )}

      {readiness.confidence === "low" && (
        <div className="notice">
          <IconAlert />
          <span>
            Readiness and impact-evidence levels are a <strong>{readiness.assessor}</strong> (
            {partialDate(readiness.assessed_on)}, confidence: low) built from public sources.
            Validate with the founders before relying on them.
          </span>
        </div>
      )}

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <div className="card stat">
          <span className="label">Investment potential</span>
          <span className="hero-value">{score(scores.potential)}</span>
          <span className="sub">
            {scores.imbalance_penalty > 0
              ? `Includes −${scores.imbalance_penalty} imbalance penalty`
              : "out of 100"}
          </span>
        </div>
        <div className="card stat">
          <span className="label">Readiness index (KTH IRL)</span>
          <span className="value">{score(scores.readiness)}</span>
          <Meter value={scores.readiness} label="Readiness index" showValue={false} />
          <span className="sub">
            TRL {readiness.trl} · BRL {readiness.brl} · spread {scores.readiness_spread}
          </span>
        </div>
        <div className="card stat">
          <span className="label">Ocean impact readiness</span>
          <span className="value">{score(scores.ocean_impact)}</span>
          <Meter value={scores.ocean_impact} label="Ocean impact" showValue={false} />
          <span className="sub">
            Best evidence: {scores.ocean_evidence_label} · areas{" "}
            {scores.ocean_areas_covered.join(", ") || "none"}
          </span>
        </div>
        <div className="card stat">
          <span className="label">Funding momentum</span>
          <span className="value">{score(scores.momentum)}</span>
          <Meter value={scores.momentum} label="Funding momentum" showValue={false} />
          <span className="sub">Last round {partialDate(s.last_round_on)}</span>
        </div>
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <div className="stack">
          <section className="card card-pad">
            <div className="card-head">
              <h2>Readiness profile</h2>
              <span className="small muted">KTH Innovation Readiness Level, 1–9</span>
            </div>
            <ReadinessProfile levels={s.levels} lagging={scores.lagging_dimensions} />
            {readiness.rationale && (
              <p className="small secondary" style={{ marginTop: 14 }}>
                {readiness.rationale}
              </p>
            )}
          </section>

          <section className="card card-pad">
            <div className="card-head">
              <h2>About</h2>
            </div>
            <p className="secondary">{s.description}</p>
          </section>

          <section className="card card-pad">
            <div className="card-head">
              <h2>Funding rounds</h2>
              <span className="small muted">
                Total disclosed ≈ {compactMoney(s.total_disclosed_usd)}
              </span>
            </div>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Round</th>
                    <th>Date</th>
                    <th className="num">Amount</th>
                    <th>Lead</th>
                  </tr>
                </thead>
                <tbody>
                  {s.funding_rounds.map((r, i) => (
                    <tr key={i}>
                      <td>
                        {stageLabel(r.round_type)}
                        {r.source_url && (
                          <>
                            {" "}
                            <a
                              href={r.source_url}
                              target="_blank"
                              rel="noreferrer"
                              aria-label="Source"
                            >
                              <IconExternal />
                            </a>
                          </>
                        )}
                      </td>
                      <td className="tabular">{partialDate(r.announced_on)}</td>
                      <td className="num">
                        {r.amount != null && r.currency
                          ? compactMoney(r.amount, r.currency)
                          : "Undisclosed"}
                      </td>
                      <td className="small secondary">
                        {r.lead_investors}
                        {r.notes && <div className="muted">{r.notes}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div className="stack">
          <section className="card card-pad">
            <div className="card-head">
              <h2>Ocean impact</h2>
              <span className="small muted">Ocean Impact Navigator · evidence 0–4</span>
            </div>
            <OceanImpact kpis={s.ocean_kpis} />
          </section>

          <section className="card card-pad">
            <div className="card-head">
              <h2>Analyst notes</h2>
            </div>
            <form onSubmit={submitNote} className="stack" style={{ gap: 8, marginBottom: 14 }}>
              <label className="visually-hidden" htmlFor="note">
                New note
              </label>
              <textarea
                id="note"
                className="textarea"
                placeholder="Add a diligence note…"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              <div>
                <Button className="btn btn-primary" disabled={saving || !note.trim()}>
                  {saving ? "Saving…" : "Add note"}
                </Button>
              </div>
            </form>
            <div className="notes">
              {s.notes.length === 0 && <p className="small muted">No notes yet.</p>}
              {s.notes.map((n) => (
                <div className="note" key={n.id}>
                  <p>{n.body}</p>
                  <span className="small muted">
                    {n.author} · {new Date(n.created_at + "Z").toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </section>

          <section className="card card-pad">
            <div className="card-head">
              <h2>Sources</h2>
            </div>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {s.sources.map((src) => (
                <li key={src.url}>
                  <a href={src.url} target="_blank" rel="noreferrer">
                    {src.title}
                  </a>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
