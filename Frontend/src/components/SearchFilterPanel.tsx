import { DIMENSIONS, PIPELINE_STAGES, type PipelineStage } from "../api/types";
import { PIPELINE_LABELS, stageLabel } from "../lib/format";
import type { SearchFilters } from "../lib/discover-search";
import { useAppData } from "../state/AppData";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group";

type Props = {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
};

/** Every structured filter, edited directly. Free-text terms stay as chips. */
export function SearchFilterPanel({ filters, onChange }: Props) {
  const { startups, vocabulary, frameworks } = useAppData();
  const set = (patch: Partial<SearchFilters>) => onChange({ ...filters, ...patch });
  const stages = [...new Set(startups.map((s) => s.stage))].sort();

  return (
    <div className="mt-4 grid gap-5 border-t border-border pt-4 md:grid-cols-2">
      <Facet
        label="Stage"
        options={stages.map((s) => ({ value: s, label: stageLabel(s) }))}
        selected={filters.stages}
        onChange={(stages) => set({ stages })}
      />
      <Facet
        label="Region"
        options={[...new Set(startups.map((s) => s.region))]
          .sort()
          .map((r) => ({ value: r, label: r }))}
        selected={filters.regions}
        onChange={(regions) => set({ regions })}
      />
      <Facet
        label="Sector"
        options={vocabulary.sectors.map((s) => ({ value: s, label: s }))}
        selected={filters.sectors}
        onChange={(sectors) => set({ sectors })}
      />
      <Facet
        label="Ocean impact area"
        options={frameworks.ocean_impact_areas.map((a) => ({
          value: a.code,
          label: `${a.code} · ${a.name}`,
        }))}
        selected={filters.impactAreas}
        onChange={(impactAreas) => set({ impactAreas })}
      />
      <Facet
        label="Pipeline"
        options={PIPELINE_STAGES.map((p) => ({ value: p, label: PIPELINE_LABELS[p] }))}
        selected={filters.pipeline}
        onChange={(pipeline) => set({ pipeline: pipeline as PipelineStage[] })}
      />
      <fieldset className="min-w-0">
        <legend className="mb-2 text-xs font-bold text-muted-foreground">
          Minimum readiness (KTH IRL)
        </legend>
        <div className="grid grid-cols-3 gap-2">
          {DIMENSIONS.map((d) => (
            <label key={d.key} className="field">
              {d.code}
              <select
                className="select"
                value={filters.minLevels[d.key] ?? ""}
                onChange={(e) => {
                  const minLevels = { ...filters.minLevels };
                  if (e.target.value) minLevels[d.key] = Number(e.target.value);
                  else delete minLevels[d.key];
                  set({ minLevels });
                }}
              >
                <option value="">Any</option>
                {Array.from({ length: 9 }, (_, i) => i + 1).map((n) => (
                  <option key={n} value={n}>
                    ≥ {n}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  );
}

/** Multi-select facet as a row of toggle pills. */
function Facet({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (selected: string[]) => void;
}) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-2 text-xs font-bold text-muted-foreground">{label}</legend>
      <ToggleGroup
        type="multiple"
        variant="outline"
        size="sm"
        value={selected}
        onValueChange={onChange}
        className="flex-wrap justify-start gap-1.5"
      >
        {options.map((o) => (
          <ToggleGroupItem
            key={o.value}
            value={o.value}
            className="rounded-full px-3 text-xs data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-primary-foreground"
          >
            {o.label}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </fieldset>
  );
}
