import type { Thesis } from "../../lib/matching";
import type { Framework } from "../../api/types";
import { TextField } from "../Controls";
export function ThesisEditor({
  thesis,
  editableName,
  sectors,
  impactAreas,
  onChange,
}: {
  thesis: Thesis;
  editableName: boolean;
  sectors: string[];
  impactAreas: Framework["ocean_impact_areas"];
  onChange: (t: Thesis) => void;
}) {
  return (
    <div className="stack">
      {editableName && (
        <TextField
          label="Thesis name"
          value={thesis.name}
          onChange={(name) => onChange({ ...thesis, name })}
        />
      )}
      <fieldset>
        <legend>Sectors</legend>
        <div className="check-list">
          {sectors.map((s) => (
            <label key={s}>
              <input
                type="checkbox"
                checked={thesis.sectors.includes(s)}
                onChange={(e) =>
                  onChange({
                    ...thesis,
                    sectors: e.target.checked
                      ? [...thesis.sectors, s]
                      : thesis.sectors.filter((v) => v !== s),
                  })
                }
              />
              {s}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend>Impact areas</legend>
        <div className="check-list">
          {impactAreas.map((a) => (
            <label key={a.code}>
              <input
                type="checkbox"
                checked={thesis.impactAreas.includes(a.code)}
                onChange={(e) =>
                  onChange({
                    ...thesis,
                    impactAreas: e.target.checked
                      ? [...thesis.impactAreas, a.code]
                      : thesis.impactAreas.filter((v) => v !== a.code),
                  })
                }
              />
              {a.name}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="field">
        Minimum TRL · {thesis.minTrl}
        <input
          type="range"
          min={1}
          max={9}
          value={thesis.minTrl}
          onChange={(e) => onChange({ ...thesis, minTrl: Number(e.target.value) })}
        />
      </label>
      <label className="field">
        Minimum potential · {thesis.minPotential}
        <input
          type="range"
          min={0}
          max={100}
          value={thesis.minPotential}
          onChange={(e) => onChange({ ...thesis, minPotential: Number(e.target.value) })}
        />
      </label>
    </div>
  );
}
