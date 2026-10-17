import { useId } from "react";
import type { Option } from "./types";
import { control } from "./styles";

/** A labelled <select> whose first option means "no filter". */
export function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Option<string>[];
  onChange: (value: string) => void;
}) {
  const id = useId();
  return (
    <>
      <label className="sr-only" htmlFor={id}>
        {label}
      </label>
      <select id={id} className={control} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{label}: All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </>
  );
}
