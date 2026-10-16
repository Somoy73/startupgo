import { useId } from "react";
import { FUNDING_STAGES, type Frameworks } from "../../api/types";
import { stageLabel } from "../../lib/format";
import type { Thesis } from "../../lib/matching";
import { REGIONS } from "../../lib/regions";
import { OptionalLevel, TextField, ToggleGroup } from "../Controls";

const OCEAN_THRESHOLDS = [20, 30, 40, 50, 60, 70];

interface Props {
  thesis: Thesis;
  editableName: boolean;
  sectors: string[];
  impactAreas: Frameworks["ocean_impact_areas"];
  onChange: (thesis: Thesis) => void;
}

export function ThesisEditor({ thesis, editableName, sectors, impactAreas, onChange }: Props) {
  const oceanId = useId();
  const weightId = useId();
  const set = (patch: Partial<Thesis>) => onChange({ ...thesis, ...patch });
  const qualityPct = Math.round(thesis.qualityWeight * 100);

  return (
    <div className="stack" style={{ gap: 14 }}>
      {editableName && <TextField label="Thesis name" value={thesis.name} onChange={(name) => set({ name })} />}
      <ToggleGroup
        label="Stages"
        options={FUNDING_STAGES.map((s) => ({ value: s, label: stageLabel(s) }))}
        selected={thesis.stages}
        onChange={(stages) => set({ stages })}
      />
      <ToggleGroup
        label="Sectors"
        options={sectors.map((s) => ({ value: s, label: s }))}
        selected={thesis.sectors}
        onChange={(sectors) => set({ sectors })}
      />
      <ToggleGroup
        label="Regions"
        options={REGIONS.map((r) => ({ value: r.id, label: r.label }))}
        selected={thesis.regions}
        onChange={(regions) => set({ regions })}
      />
      <ToggleGroup
        label="Ocean impact areas"
        options={impactAreas.map((a) => ({ value: a.code, label: `${a.code} · ${a.name}` }))}
        selected={thesis.impactAreas}
        onChange={(impactAreas) => set({ impactAreas })}
      />
      <div className="form-grid three">
        <OptionalLevel label="Min TRL" value={thesis.minTrl} onChange={(minTrl) => set({ minTrl })} />
        <OptionalLevel label="Min BRL" value={thesis.minBrl} onChange={(minBrl) => set({ minBrl })} />
        <div className="field">
          <label htmlFor={oceanId}>Min ocean impact</label>
          <select
            id={oceanId}
            className="select"
            value={thesis.minOceanImpact ?? ""}
            onChange={(e) => set({ minOceanImpact: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">Any</option>
            {OCEAN_THRESHOLDS.map((n) => (
              <option key={n} value={n}>
                ≥ {n}
              </option>
            ))}
          </select>
        </div>
      </div>
      <div className="field">
        <label htmlFor={weightId}>
          Ranking: {100 - qualityPct}% thesis fit · {qualityPct}% investment potential
        </label>
        <input
          id={weightId}
          type="range"
          min={0}
          max={100}
          step={10}
          value={qualityPct}
          onChange={(e) => set({ qualityWeight: Number(e.target.value) / 100 })}
        />
      </div>
    </div>
  );
}
