import { DIMENSIONS, FUNDING_STAGES, PIPELINE_STAGES, type PipelineStage } from "@/api/types";
import { OptionalLevel, ToggleGroup } from "@/components/ui";
import { PIPELINE_LABELS, stageLabel } from "@/lib/format";
import { REGIONS, type Region } from "@/lib/regions";
import type { SearchFilters } from "@/lib/search";
import { useAppData } from "@/state/AppData";

interface Props {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
}

/** Every structured search filter, edited directly. Keywords stay as chips. */
export function SearchFilterPanel({ filters, onChange }: Props) {
  const { vocabulary, frameworks } = useAppData();
  const set = (patch: Partial<SearchFilters>) => onChange({ ...filters, ...patch });

  return (
    <div className="mt-3 grid gap-4 border-t border-line pt-3.5 md:grid-cols-2">
      <ToggleGroup
        label="Stage"
        options={FUNDING_STAGES.map((s) => ({ value: s, label: stageLabel(s) }))}
        selected={filters.stages}
        onChange={(stages) => set({ stages })}
      />
      <ToggleGroup
        label="Region"
        options={REGIONS.map((r) => ({ value: r.id, label: r.label }))}
        selected={filters.regions}
        onChange={(regions) => set({ regions: regions as Region[] })}
      />
      <ToggleGroup
        label="Sector"
        options={vocabulary.sectors.map((s) => ({ value: s, label: s }))}
        selected={filters.sectors}
        onChange={(sectors) => set({ sectors })}
      />
      <ToggleGroup
        label="Ocean impact area"
        options={(frameworks?.ocean_impact_areas ?? []).map((a) => ({ value: a.code, label: `${a.code} · ${a.name}` }))}
        selected={filters.impactAreas}
        onChange={(impactAreas) => set({ impactAreas })}
      />
      <ToggleGroup
        label="Pipeline"
        options={PIPELINE_STAGES.map((p) => ({ value: p, label: PIPELINE_LABELS[p] }))}
        selected={filters.pipeline}
        onChange={(pipeline) => set({ pipeline: pipeline as PipelineStage[] })}
      />
      <fieldset className="m-0 min-w-0 border-0 p-0">
        <legend className="mb-1.5 p-0 text-sm text-muted">Minimum readiness (KTH IRL)</legend>
        <div className="grid grid-cols-3 gap-2">
          {DIMENSIONS.map((d) => (
            <OptionalLevel
              key={d.key}
              label={d.code}
              value={filters.minLevels[d.key] ?? null}
              onChange={(level) => {
                const minLevels = { ...filters.minLevels };
                if (level === null) delete minLevels[d.key];
                else minLevels[d.key] = level;
                set({ minLevels });
              }}
            />
          ))}
        </div>
      </fieldset>
    </div>
  );
}
