import { useId } from "react";
import { FUNDING_STAGES, type FundingStage } from "@/api/types";
import type { CompanyDraft, DraftErrors } from "@/lib/assessment";
import { stageLabel } from "@/lib/format";
import type { Vocabulary } from "@/lib/search";
import { control, fieldLabel, formGrid, TextField } from "@/components/ui";

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
    <div className={formGrid}>
      {field("name", "Company name", { required: true })}
      {field("tagline", "One-line tagline", { required: true })}
      <div className="col-span-full">{field("description", "What they do", { required: true, multiline: true })}</div>
      {field("sector", "Sector", { required: true, suggestions: vocabulary.sectors })}
      <div className="flex flex-col gap-1">
        <label htmlFor={stageId} className={fieldLabel}>
          Funding stage
        </label>
        <select
          id={stageId}
          className={control}
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

      <h3 className="col-span-full mt-2">
        Latest funding round <span className="text-small text-muted">(optional)</span>
      </h3>
      {field("roundAmount", "Amount", { placeholder: "e.g. 500000" })}
      {field("roundCurrency", "Currency", { placeholder: "e.g. EUR" })}
      {field("roundDate", "Announced", { placeholder: "YYYY-MM" })}
      {field("roundLead", "Lead investor(s)")}
    </div>
  );
}
