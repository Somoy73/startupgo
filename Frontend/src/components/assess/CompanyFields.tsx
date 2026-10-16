import { useId } from "react";
import { FUNDING_STAGES, type FundingStage } from "../../api/types";
import type { CompanyDraft, DraftErrors } from "../../lib/assessment";
import { stageLabel } from "../../lib/format";
import type { Vocabulary } from "../../lib/search";
import { TextField } from "../Controls";

interface Props {
  company: CompanyDraft;
  errors: DraftErrors;
  vocabulary: Vocabulary;
  onChange: (patch: Partial<CompanyDraft>) => void;
}

export function CompanyFields({ company, errors, vocabulary, onChange }: Props) {
  const stageId = useId();
  const field = (key: keyof CompanyDraft, label: string, extra: Partial<Parameters<typeof TextField>[0]> = {}) => (
    <TextField
      label={label}
      value={company[key]}
      error={errors[`company.${key}`]}
      onChange={(v) => onChange({ [key]: v })}
      {...extra}
    />
  );

  return (
    <div className="form-grid">
      {field("name", "Company name", { required: true })}
      {field("tagline", "One-line tagline", { required: true })}
      <div className="span-2">{field("description", "What they do", { required: true, multiline: true })}</div>
      {field("sector", "Sector", { required: true, suggestions: vocabulary.sectors })}
      <div className="field">
        <label htmlFor={stageId}>Funding stage</label>
        <select
          id={stageId}
          className="select"
          value={company.stage}
          onChange={(e) => onChange({ stage: e.target.value as FundingStage })}
        >
          {FUNDING_STAGES.map((s) => (
            <option key={s} value={s}>
              {stageLabel(s)}
            </option>
          ))}
        </select>
      </div>
      {field("country", "Country", { required: true, suggestions: vocabulary.countries })}
      {field("city", "City")}
      {field("foundedYear", "Founded (year)", { placeholder: "e.g. 2024" })}
      {field("website", "Website", { placeholder: "https://" })}

      <h3 className="span-2" style={{ marginTop: 8 }}>
        Latest funding round <span className="muted small">(optional)</span>
      </h3>
      {field("roundAmount", "Amount", { placeholder: "e.g. 500000" })}
      {field("roundCurrency", "Currency", { placeholder: "e.g. EUR" })}
      {field("roundDate", "Announced", { placeholder: "YYYY-MM" })}
      {field("roundLead", "Lead investor(s)")}
    </div>
  );
}
