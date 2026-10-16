import { useId } from "react";

interface Option<T extends string> {
  value: T;
  label: string;
}

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
      <label className="visually-hidden" htmlFor={id}>
        {label}
      </label>
      <select id={id} className="select" value={value} onChange={(e) => onChange(e.target.value)}>
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

/** Multi-select as a row of toggle buttons. */
export function ToggleGroup<T extends string>({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: Option<T>[];
  selected: T[];
  onChange: (selected: T[]) => void;
}) {
  const toggle = (value: T) =>
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  return (
    <fieldset className="toggle-group">
      <legend>{label}</legend>
      <div>
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            className="toggle"
            aria-pressed={selected.includes(o.value)}
            onClick={() => toggle(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

/** Single choice from a short ordered scale (levels, evidence) as a segmented control. */
export function Segmented({
  label,
  values,
  value,
  onChange,
  describe,
}: {
  label: string;
  values: number[];
  value: number;
  onChange: (value: number) => void;
  describe?: (value: number) => string;
}) {
  return (
    <div className="segmented" role="radiogroup" aria-label={label}>
      {values.map((v) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={v === value}
          className={v <= value && v > 0 ? "filled" : ""}
          title={describe?.(v)}
          onClick={() => onChange(v)}
        >
          {v}
        </button>
      ))}
    </div>
  );
}

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
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        className="select"
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

/** Labelled text input or textarea with an inline error message. */
export function TextField({
  label,
  value,
  onChange,
  error,
  multiline = false,
  suggestions,
  placeholder,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  multiline?: boolean;
  suggestions?: string[];
  placeholder?: string;
  required?: boolean;
}) {
  const id = useId();
  const listId = suggestions ? `${id}-list` : undefined;
  const common = {
    id,
    value,
    placeholder,
    required,
    "aria-invalid": Boolean(error),
    "aria-describedby": error ? `${id}-error` : undefined,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange(e.target.value),
  };
  return (
    <div className="field">
      <label htmlFor={id}>
        {label}
        {required && <span aria-hidden> *</span>}
      </label>
      {multiline ? (
        <textarea className="textarea" {...common} />
      ) : (
        <input className="input" list={listId} {...common} />
      )}
      {suggestions && (
        <datalist id={listId}>
          {suggestions.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      )}
      {error && (
        <span id={`${id}-error`} className="field-error">
          {error}
        </span>
      )}
    </div>
  );
}
