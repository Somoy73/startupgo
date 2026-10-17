import { useEffect, useId, useRef, useState } from "react";
import { LuColumns3 } from "react-icons/lu";
import { button } from "@/components/ui";
import { COLUMNS, DEFAULT_COLUMNS } from "./columns";

interface Props {
  columns: string[];
  onChange: (columns: string[]) => void;
}

/** "Columns" menu: choose which optional columns the table shows. */
export function ColumnPicker({ columns, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const optional = COLUMNS.filter((c) => !c.locked);

  useEffect(() => {
    if (!open) return;
    const onPointer = (e: PointerEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const toggle = (id: string) => onChange(columns.includes(id) ? columns.filter((c) => c !== id) : [...columns, id]);
  const shown = optional.filter((c) => columns.includes(c.id)).length;

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        className={button()}
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((o) => !o)}
      >
        <LuColumns3 size={15} />
        Columns
        <span className="text-small text-muted tabular-nums">
          {shown}/{optional.length}
        </span>
      </button>
      {open && (
        <div
          id={menuId}
          className="absolute top-full right-0 z-20 mt-1.5 w-60 rounded-card border border-line bg-surface p-2 shadow-card"
        >
          <fieldset className="m-0 border-0 p-0">
            <legend className="px-2 pt-1 pb-1.5 text-small text-muted">Show columns</legend>
            {optional.map((c) => (
              <label
                key={c.id}
                className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-2"
              >
                <input type="checkbox" checked={columns.includes(c.id)} onChange={() => toggle(c.id)} />
                {c.header}
              </label>
            ))}
          </fieldset>
          <button
            type="button"
            className="mt-1 w-full cursor-pointer rounded-md border-0 bg-transparent px-2 py-1.5 text-left text-small text-accent-ink hover:bg-surface-2"
            onClick={() => onChange(DEFAULT_COLUMNS)}
          >
            Reset to default
          </button>
        </div>
      )}
    </div>
  );
}
