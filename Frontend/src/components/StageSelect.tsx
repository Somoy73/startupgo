import { PIPELINE_STAGES, type PipelineStage } from "@/api/types";
import { PIPELINE_LABELS } from "@/lib/format";
import { control, cx, fieldLabel } from "@/components/ui";

interface Props {
  id: string;
  label: string;
  value: PipelineStage;
  onChange: (stage: PipelineStage) => void;
  /** Small select with a screen-reader-only label (for cards). */
  compact?: boolean;
}

/** Menu for moving a deal between pipeline stages. */
export function StageSelect({ id, label, value, onChange, compact = false }: Props) {
  const select = (
    <select
      id={id}
      className={cx(control, compact && "text-small")}
      value={value}
      onChange={(e) => onChange(e.target.value as PipelineStage)}
    >
      {PIPELINE_STAGES.map((p) => (
        <option key={p} value={p}>
          {PIPELINE_LABELS[p]}
        </option>
      ))}
    </select>
  );

  if (compact) {
    return (
      <>
        <label className="sr-only" htmlFor={id}>
          {label}
        </label>
        {select}
      </>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className={fieldLabel}>
        {label}
      </label>
      {select}
    </div>
  );
}
