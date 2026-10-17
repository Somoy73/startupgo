import { Button } from "../ui/button";
import { Columns3 } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import { COLUMNS, DEFAULT_COLUMNS } from "./columns";

type Props = {
  columns: string[];
  onChange: (columns: string[]) => void;
};

/** "Columns" menu: choose which optional columns the table shows. */
export function ColumnPicker({ columns, onChange }: Props) {
  const optional = COLUMNS.filter((c) => !c.locked);
  const shown = optional.filter((c) => columns.includes(c.id)).length;
  const toggle = (id: string) =>
    onChange(columns.includes(id) ? columns.filter((c) => c !== id) : [...columns, id]);

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button type="button" className="btn inline-flex items-center gap-2">
          <Columns3 aria-hidden className="size-4" />
          Columns
          <span className="small muted tabular">
            {shown}/{optional.length}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-60 p-2">
        <fieldset>
          <legend className="px-2 pt-1 pb-1.5 text-xs font-semibold text-muted-foreground">
            Show columns
          </legend>
          {optional.map((c) => (
            <label
              key={c.id}
              className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-wash"
            >
              <input
                type="checkbox"
                checked={columns.includes(c.id)}
                onChange={() => toggle(c.id)}
              />
              {c.header}
            </label>
          ))}
        </fieldset>
        <Button
          type="button"
          className="mt-1 h-auto w-full cursor-pointer rounded-md px-2 py-1.5 text-sm"
          onClick={() => onChange(DEFAULT_COLUMNS)}
        >
          Reset to default
        </Button>
      </PopoverContent>
    </Popover>
  );
}
