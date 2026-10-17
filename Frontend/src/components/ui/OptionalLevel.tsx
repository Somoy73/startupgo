import { useId } from "react";
import { control, fieldLabel } from "./styles";

/** Optional number input; empty means "no constraint". */
export function OptionalLevel({
  label,
  value,
  onChange,
  max = 9,
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  max?: number;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className={fieldLabel}>
        {label}
      </label>
      <select
        id={id}
        className={control}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">Any</option>
        {Array.from({ length: max }, (_, i) => i + 1).map((n) => (
          <option key={n} value={n}>
            ≥ {n}
          </option>
        ))}
      </select>
    </div>
  );
}
