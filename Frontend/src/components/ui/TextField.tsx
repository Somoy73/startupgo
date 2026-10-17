import { useId } from "react";
import { control, cx, fieldLabel, textarea } from "./styles";

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
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className={fieldLabel}>
        {label}
        {required && <span aria-hidden> *</span>}
      </label>
      {multiline ? (
        <textarea className={textarea} {...common} />
      ) : (
        <input className={cx(control, "w-full")} list={listId} {...common} />
      )}
      {suggestions && (
        <datalist id={listId}>
          {suggestions.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      )}
      {error && (
        <span id={`${id}-error`} className="text-sm text-critical">
          {error}
        </span>
      )}
    </div>
  );
}
