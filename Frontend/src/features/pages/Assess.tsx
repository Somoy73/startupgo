import { Button } from "../../components/ui/button";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "../../lib/navigation";
import { api } from "../../api/client";
import type { Confidence, DimensionKey, StartupDetail } from "../../api/types";
import { CompanyFields } from "../../components/assess/CompanyFields";
import { ImpactFields } from "../../components/assess/ImpactFields";
import { ReadinessFields } from "../../components/assess/ReadinessFields";
import { ScorePreview } from "../../components/assess/ScorePreview";
import { TextField } from "../../components/Controls";
import { IconBack } from "../../components/Icons";
import {
  assessmentFromStartup,
  emptyAssessment,
  emptyCompany,
  toAssessmentInput,
  toPreviewInput,
  toStartupInput,
  validateAssessment,
  validateCompany,
  type AssessmentDraft,
  type CompanyDraft,
  type DraftErrors,
} from "../../lib/assessment";
import { useAsync } from "../../lib/useAsync";
import { useScorePreview } from "../../lib/useScorePreview";
import { useAppData } from "../../state/AppData";

const CONFIDENCE: Confidence[] = ["low", "medium", "high"];

/** /assess → new startup; /assess/:slug → new assessment of an existing startup. */
export function Assess() {
  const { slug } = useParams();
  const existing = useAsync(() => (slug ? api.startup(slug) : Promise.resolve(null)), [slug]);

  if (existing.error) return <p className="empty error">{existing.error}</p>;
  if (existing.loading) return <p className="empty">Loading…</p>;
  // key resets the form when switching between startups
  return <AssessForm key={slug ?? "new"} startup={existing.data ?? null} />;
}

function AssessForm({ startup }: { startup: StartupDetail | null }) {
  const { startups, frameworks, vocabulary, upsertStartup } = useAppData();
  const navigate = useNavigate();
  const [company, setCompany] = useState<CompanyDraft>(emptyCompany);
  const [draft, setDraft] = useState<AssessmentDraft>(() =>
    startup ? assessmentFromStartup(startup) : emptyAssessment(),
  );
  const [submitted, setSubmitted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const isNew = startup === null;
  const previewInput = useMemo(
    () =>
      isNew
        ? toPreviewInput(draft, company.stage, company.roundDate.trim() || null)
        : toPreviewInput(draft, startup.stage, startup.last_round_on),
    [draft, company.stage, company.roundDate, isNew, startup],
  );
  const preview = useScorePreview(previewInput);

  const validationErrors = useMemo<DraftErrors>(
    () => ({ ...validateAssessment(draft), ...(isNew ? validateCompany(company) : {}) }),
    [draft, company, isNew],
  );
  // Errors only show after the first submit attempt, then update live as fields are fixed.
  const errors = submitted ? validationErrors : {};
  const errorCount = Object.keys(errors).length;

  const update = (patch: Partial<AssessmentDraft>) => setDraft((d) => ({ ...d, ...patch }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    if (Object.keys(validationErrors).length) return;

    setSaving(true);
    setSaveError(null);
    try {
      const saved = isNew
        ? await api.createStartup(toStartupInput(company, draft))
        : await api.addAssessment(startup.slug, toAssessmentInput(draft));
      upsertStartup(saved);
      navigate(`/startups/${saved.slug}`);
    } catch (err) {
      setSaveError((err as Error).message);
      setSaving(false);
    }
  };

  if (!frameworks) return <p className="empty">Loading frameworks…</p>;

  return (
    <>
      {startup && (
        <Link to={`/startups/${startup.slug}`} className="back">
          <IconBack /> {startup.name}
        </Link>
      )}
      <div className="page-head">
        <div>
          <h1>{isNew ? "Assess a new startup" : `Assess ${startup.name}`}</h1>
          <p>
            {isNew
              ? "Add a company and score its readiness and ocean impact. It joins your deal flow as Sourced."
              : `Pre-filled from the current assessment (${startup.readiness.assessor}, ${startup.readiness.assessed_on}). Saving adds a new dated snapshot.`}
          </p>
        </div>
        <StartupSwitcher
          current={startup?.slug ?? ""}
          options={startups.map((s) => ({ slug: s.slug, name: s.name }))}
        />
      </div>

      <form className="assess-layout" onSubmit={submit} noValidate>
        <div className="stack">
          {isNew && (
            <section className="card card-pad">
              <div className="card-head">
                <h2>1 · Company</h2>
              </div>
              <CompanyFields
                company={company}
                errors={errors}
                vocabulary={vocabulary}
                onChange={(patch) => setCompany((c) => ({ ...c, ...patch }))}
              />
            </section>
          )}

          <section className="card card-pad">
            <div className="card-head">
              <h2>{isNew ? "2" : "1"} · Readiness</h2>
              <span className="small muted">KTH Innovation Readiness Level, 1–9</span>
            </div>
            <ReadinessFields
              levels={draft.levels}
              dimensions={frameworks.readiness_dimensions}
              onChange={(key: DimensionKey, level) =>
                update({ levels: { ...draft.levels, [key]: level } })
              }
            />
          </section>

          <section className="card card-pad">
            <div className="card-head">
              <h2>{isNew ? "3" : "2"} · Ocean impact evidence</h2>
              <span className="small muted">Ocean Impact Navigator</span>
            </div>
            <ImpactFields
              kpis={draft.kpis}
              framework={frameworks}
              errors={errors}
              onChange={(code, kpi) => update({ kpis: { ...draft.kpis, [code]: kpi } })}
            />
          </section>

          <section className="card card-pad">
            <div className="card-head">
              <h2>{isNew ? "4" : "3"} · Sign-off</h2>
            </div>
            <div className="form-grid">
              <TextField
                label="Assessor"
                value={draft.assessor}
                onChange={(assessor) => update({ assessor })}
                error={errors["assessor"]}
                placeholder="Your name"
                required
              />
              <fieldset className="toggle-group">
                <legend>Confidence</legend>
                <div>
                  {CONFIDENCE.map((c) => (
                    <Button
                      key={c}
                      type="button"
                      className="toggle"
                      aria-pressed={draft.confidence === c}
                      onClick={() => update({ confidence: c })}
                    >
                      {c}
                    </Button>
                  ))}
                </div>
              </fieldset>
              <div className="span-2">
                <TextField
                  label="Rationale"
                  value={draft.rationale}
                  onChange={(rationale) => update({ rationale })}
                  placeholder="What evidence supports these levels? What would move them up?"
                  multiline
                />
              </div>
            </div>
          </section>
        </div>

        <div className="assess-side">
          <ScorePreview
            preview={preview.scores}
            current={startup?.scores ?? null}
            error={preview.error}
          />
          {errorCount > 0 && (
            <p className="small error" role="alert">
              Fix {errorCount} field{errorCount > 1 ? "s" : ""} before saving.
            </p>
          )}
          {saveError && (
            <p className="small error" role="alert">
              Couldn't save: {saveError}
            </p>
          )}
          <Button className="btn btn-primary btn-block" disabled={saving}>
            {saving ? "Saving…" : isNew ? "Add startup" : "Save assessment"}
          </Button>
        </div>
      </form>
    </>
  );
}

function StartupSwitcher({
  current,
  options,
}: {
  current: string;
  options: { slug: string; name: string }[];
}) {
  const navigate = useNavigate();
  return (
    <div className="field">
      <label htmlFor="assess-target">Startup</label>
      <select
        id="assess-target"
        className="select"
        value={current}
        onChange={(e) => navigate(e.target.value ? `/assess/${e.target.value}` : "/assess")}
      >
        <option value="">+ New startup</option>
        {options.map((o) => (
          <option key={o.slug} value={o.slug}>
            {o.name}
          </option>
        ))}
      </select>
    </div>
  );
}
