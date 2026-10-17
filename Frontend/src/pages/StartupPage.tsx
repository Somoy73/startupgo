import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { LuExternalLink, LuTriangleAlert } from "react-icons/lu";
import { api } from "@/api/client";
import type { PipelineStage } from "@/api/types";
import { OceanImpact } from "@/components/OceanImpact";
import { ReadinessProfile } from "@/components/ReadinessProfile";
import { StageSelect } from "@/components/StageSelect";
import {
  BackLink,
  BandBadge,
  button,
  cx,
  EmptyState,
  num,
  PageHeader,
  Section,
  stack,
  StatCard,
  table,
  td,
  textarea,
  th,
} from "@/components/ui";
import { compactMoney, partialDate, score, stageLabel } from "@/lib/format";
import { useAsync } from "@/lib/useAsync";
import { useAppData } from "@/state/AppData";

export function StartupPage() {
  const { slug = "" } = useParams();
  const { upsertStartup } = useAppData();
  const { data: s, error, loading, setData } = useAsync(() => api.startup(slug), [slug]);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (error) return <EmptyState error>{error}</EmptyState>;
  if (loading || !s) return <EmptyState>Loading…</EmptyState>;

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
      <BackLink to="/">Deal flow</BackLink>
      <PageHeader
        title={s.name}
        badge={<BandBadge band={scores.band} />}
        description={s.tagline}
        meta={
          <>
            {s.sector} · {[s.city, s.country].filter((x, i, a) => x && a.indexOf(x) === i).join(", ")}
            {s.founded_year && ` · Founded ${s.founded_year}`} · {stageLabel(s.stage)}
            {s.website && (
              <>
                {" · "}
                <a href={s.website} target="_blank" rel="noreferrer">
                  Website <LuExternalLink size={13} className="inline" />
                </a>
              </>
            )}
          </>
        }
        actions={
          <div className="flex flex-wrap items-end gap-2">
            <Link to={`/assess/${s.slug}`} className={button()}>
              Re-assess
            </Link>
            <StageSelect id="stage" label="Pipeline stage" value={s.pipeline_stage} onChange={changeStage} />
          </div>
        }
      />

      {actionError && <p className="mb-3 text-small text-critical">{actionError}</p>}

      {readiness.confidence === "low" && (
        <div className="mb-4 flex items-start gap-2.5 rounded-lg bg-surface-2 px-3.5 py-2.5 text-note text-fg-2">
          <LuTriangleAlert className="mt-0.5 size-4.5 flex-none text-warning" />
          <span>
            Readiness and impact-evidence levels are a <strong>{readiness.assessor}</strong> (
            {partialDate(readiness.assessed_on)}, confidence: low) built from public sources. Validate with the founders
            before relying on them.
          </span>
        </div>
      )}

      <div className="mb-4 grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          label="Investment potential"
          value={score(scores.potential)}
          hero
          sub={scores.imbalance_penalty > 0 ? `Includes −${scores.imbalance_penalty} imbalance penalty` : "out of 100"}
        />
        <StatCard
          label="Readiness index (KTH IRL)"
          value={score(scores.readiness)}
          meter={{ value: scores.readiness, label: "Readiness index" }}
          sub={`TRL ${readiness.trl} · BRL ${readiness.brl} · spread ${scores.readiness_spread}`}
        />
        <StatCard
          label="Ocean impact readiness"
          value={score(scores.ocean_impact)}
          meter={{ value: scores.ocean_impact, label: "Ocean impact" }}
          sub={`Best evidence: ${scores.ocean_evidence_label} · areas ${scores.ocean_areas_covered.join(", ") || "none"}`}
        />
        <StatCard
          label="Funding momentum"
          value={score(scores.momentum)}
          meter={{ value: scores.momentum, label: "Funding momentum" }}
          sub={`Last round ${partialDate(s.last_round_on)}`}
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2">
        <div className={stack}>
          <Section title="Readiness profile" aside="KTH Innovation Readiness Level, 1–9">
            <ReadinessProfile levels={s.levels} lagging={scores.lagging_dimensions} />
            {readiness.rationale && <p className="mt-3.5 text-small text-fg-2">{readiness.rationale}</p>}
          </Section>

          <Section title="About">
            <p className="text-fg-2">{s.description}</p>
          </Section>

          <Section title="Funding rounds" aside={`Total disclosed ≈ ${compactMoney(s.total_disclosed_usd)}`}>
            <div className="overflow-x-auto">
              <table className={table}>
                <thead>
                  <tr>
                    <th className={th}>Round</th>
                    <th className={th}>Date</th>
                    <th className={cx(th, num)}>Amount</th>
                    <th className={th}>Lead</th>
                  </tr>
                </thead>
                <tbody>
                  {s.funding_rounds.map((r, i) => (
                    <tr key={i}>
                      <td className={td}>
                        {stageLabel(r.round_type)}
                        {r.source_url && (
                          <>
                            {" "}
                            <a href={r.source_url} target="_blank" rel="noreferrer" aria-label="Source">
                              <LuExternalLink size={13} className="inline" />
                            </a>
                          </>
                        )}
                      </td>
                      <td className={cx(td, "tabular-nums")}>{partialDate(r.announced_on)}</td>
                      <td className={cx(td, num)}>
                        {r.amount != null && r.currency ? compactMoney(r.amount, r.currency) : "Undisclosed"}
                      </td>
                      <td className={cx(td, "text-small text-fg-2")}>
                        {r.lead_investors}
                        {r.notes && <div className="text-muted">{r.notes}</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </div>

        <div className={stack}>
          <Section title="Ocean impact" aside="Ocean Impact Navigator · evidence 0–4">
            <OceanImpact kpis={s.ocean_kpis} />
          </Section>

          <Section title="Analyst notes">
            <form onSubmit={submitNote} className="mb-3.5 flex flex-col gap-2">
              <label className="sr-only" htmlFor="note">
                New note
              </label>
              <textarea
                id="note"
                className={textarea}
                placeholder="Add a diligence note…"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              <div>
                <button className={button("primary")} disabled={saving || !note.trim()}>
                  {saving ? "Saving…" : "Add note"}
                </button>
              </div>
            </form>
            <div className="flex flex-col gap-2.5">
              {s.notes.length === 0 && <p className="text-small text-muted">No notes yet.</p>}
              {s.notes.map((n) => (
                <div className="border-l-3 border-accent py-1 pl-3" key={n.id}>
                  <p className="whitespace-pre-wrap">{n.body}</p>
                  <span className="text-small text-muted">
                    {n.author} · {new Date(n.created_at + "Z").toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </Section>

          <Section title="Sources">
            <ul className="m-0 list-disc pl-4.5">
              {s.sources.map((src) => (
                <li key={src.url}>
                  <a href={src.url} target="_blank" rel="noreferrer">
                    {src.title}
                  </a>
                </li>
              ))}
            </ul>
          </Section>
        </div>
      </div>
    </>
  );
}
