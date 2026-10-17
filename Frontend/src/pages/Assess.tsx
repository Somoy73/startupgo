import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/api/client";
import type { Confidence, DimensionKey, StartupDetail } from "@/api/types";
import { CompanyFields } from "@/components/assess/CompanyFields";
import { ImpactFields } from "@/components/assess/ImpactFields";
import { ReadinessFields } from "@/components/assess/ReadinessFields";
import { ScorePreview } from "@/components/assess/ScorePreview";
import {
  BackLink,
  button,
  control,
  EmptyState,
  fieldLabel,
  formGrid,
  PageHeader,
  Section,
  stack,
  TextField,
  toggle,
} from "@/components/ui";
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
} from "@/lib/assessment";
import { useAsync } from "@/lib/useAsync";
import { useScorePreview } from "@/lib/useScorePreview";
import { useAppData } from "@/state/AppData";

const CONFIDENCE: Confidence[] = ["low", "medium", "high"];

/** /assess → new startup; /assess/:slug → new assessment of an existing startup. */
export function Assess() {
  const { slug } = useParams();
  const existing = useAsync(() => (slug ? api.startup(slug) : Promise.resolve(null)), [slug]);

  if (existing.error) return <EmptyState error>{existing.error}</EmptyState>;
  if (existing.loading) return <EmptyState>Loading…</EmptyState>;
  // key resets the form when switching between startups
  return <AssessForm key={slug ?? "new"} startup={existing.data} />;
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

  if (!frameworks) return <EmptyState>Loading frameworks…</EmptyState>;

  return (
    <>
      {startup && <BackLink to={`/startups/${startup.slug}`}>{startup.name}</BackLink>}
      <PageHeader
        title={isNew ? "Assess a new startup" : `Assess ${startup.name}`}
        description={
          isNew
            ? "Add a company and score its readiness and ocean impact. It joins your deal flow as Sourced."
            : `Pre-filled from the current assessment (${startup.readiness.assessor}, ${startup.readiness.assessed_on}). Saving adds a new dated snapshot.`
        }
        actions={
          <StartupSwitcher
            current={startup?.slug ?? ""}
            options={startups.map((s) => ({ slug: s.slug, name: s.name }))}
          />
        }
      />

      <form
        className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(0,1fr)_300px]"
        onSubmit={submit}
        noValidate
      >
        <div className={stack}>
          {isNew && (
            <Section title="1 · Company">
              <CompanyFields
                company={company}
                errors={errors}
                vocabulary={vocabulary}
                onChange={(patch) => setCompany((c) => ({ ...c, ...patch }))}
              />
            </Section>
          )}

          <Section title={`${isNew ? "2" : "1"} · Readiness`} aside="KTH Innovation Readiness Level, 1–9">
            <ReadinessFields
              levels={draft.levels}
              dimensions={frameworks.readiness_dimensions}
              onChange={(key: DimensionKey, level) => update({ levels: { ...draft.levels, [key]: level } })}
            />
          </Section>

          <Section title={`${isNew ? "3" : "2"} · Ocean impact evidence`} aside="Ocean Impact Navigator">
            <ImpactFields
              kpis={draft.kpis}
              framework={frameworks}
              errors={errors}
              onChange={(code, kpi) => update({ kpis: { ...draft.kpis, [code]: kpi } })}
            />
          </Section>

          <Section title={`${isNew ? "4" : "3"} · Sign-off`}>
            <div className={formGrid}>
              <TextField
                label="Assessor"
                value={draft.assessor}
                onChange={(assessor) => update({ assessor })}
                error={errors.assessor}
                placeholder="Your name"
                required
              />
              <fieldset className="m-0 min-w-0 border-0 p-0">
                <legend className="mb-1.5 p-0 text-sm text-muted">Confidence</legend>
                <div className="flex flex-wrap gap-1.5">
                  {CONFIDENCE.map((c) => (
                    <button
                      key={c}
                      type="button"
                      className={toggle}
                      aria-pressed={draft.confidence === c}
                      onClick={() => update({ confidence: c })}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </fieldset>
              <div className="col-span-full">
                <TextField
                  label="Rationale"
                  value={draft.rationale}
                  onChange={(rationale) => update({ rationale })}
                  placeholder="What evidence supports these levels? What would move them up?"
                  multiline
                />
              </div>
            </div>
          </Section>
        </div>

        <div className="flex flex-col gap-2.5 xl:sticky xl:top-5">
          <ScorePreview preview={preview.scores} current={startup?.scores ?? null} error={preview.error} />
          {errorCount > 0 && (
            <p className="text-small text-critical" role="alert">
              Fix {errorCount} field{errorCount > 1 ? "s" : ""} before saving.
            </p>
          )}
          {saveError && (
            <p className="text-small text-critical" role="alert">
              Couldn't save: {saveError}
            </p>
          )}
          <button className={button("primary", { block: true })} disabled={saving}>
            {saving ? "Saving…" : isNew ? "Add startup" : "Save assessment"}
          </button>
        </div>
      </form>
    </>
  );
}

function StartupSwitcher({ current, options }: { current: string; options: { slug: string; name: string }[] }) {
  const navigate = useNavigate();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor="assess-target" className={fieldLabel}>
        Startup
      </label>
      <select
        id="assess-target"
        className={control}
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
