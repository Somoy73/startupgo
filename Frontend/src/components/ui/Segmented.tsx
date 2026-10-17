import { cx } from "./styles";

/** Single choice from a short ordered scale (levels, evidence) as a segmented control. */
export function Segmented({
  label,
  values,
  value,
  onChange,
  describe,
  className,
}: {
  label: string;
  values: number[];
  value: number;
  onChange: (value: number) => void;
  describe?: (value: number) => string;
  className?: string;
}) {
  return (
    <div
      className={cx("inline-grid auto-cols-[minmax(28px,1fr)] grid-flow-col gap-0.5", className)}
      role="radiogroup"
      aria-label={label}
    >
      {values.map((v) => (
        <button
          key={v}
          type="button"
          role="radio"
          aria-checked={v === value}
          className={cx(
            "h-7 cursor-pointer border-0 text-ctl font-semibold tabular-nums first:rounded-l-md last:rounded-r-md hover:opacity-85",
            "aria-checked:opacity-100 aria-checked:outline-2 aria-checked:-outline-offset-2 aria-checked:outline-fg",
            v <= value && v > 0 ? "bg-accent text-white" : "bg-track text-fg opacity-55",
          )}
          title={describe?.(v)}
          onClick={() => onChange(v)}
        >
          {v}
        </button>
      ))}
    </div>
  );
}
