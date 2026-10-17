import { TextField } from "../Controls";
import type { CompanyDraft, DraftErrors } from "../../lib/assessment";
export function CompanyFields({
  company,
  errors,
  vocabulary,
  onChange,
}: {
  company: CompanyDraft;
  errors: DraftErrors;
  vocabulary: unknown;
  onChange: (p: Partial<CompanyDraft>) => void;
}) {
  return (
    <div className="form-grid">
      {(["name", "tagline", "sector", "country", "website", "description"] as const).map((k) => (
        <TextField
          key={k}
          label={
            {
              name: "Company name",
              tagline: "Tagline",
              sector: "Sector",
              country: "Country",
              website: "Website",
              description: "Description",
            }[k]
          }
          value={company[k]}
          error={errors[k]}
          required={["name", "sector", "country"].includes(k)}
          onChange={(v) => onChange({ [k]: v })}
        />
      ))}
      <label className="field">
        Funding stage
        <select
          className="select"
          value={company.stage}
          onChange={(e) => onChange({ stage: e.target.value })}
        >
          {["pre-seed", "seed", "series-a", "series-b", "growth"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </label>
      <label className="field">
        Last round date
        <input
          type="date"
          className="input"
          value={company.roundDate}
          onChange={(e) => onChange({ roundDate: e.target.value })}
        />
      </label>
    </div>
  );
}
