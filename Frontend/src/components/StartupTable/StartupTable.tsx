import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { StartupSummary } from "../../api/types";
import { cn } from "../../lib/utils";
import type { Sort, SortKey } from "../../lib/sort";
import { COLUMNS, type Column } from "./columns";

type Props = {
  startups: StartupSummary[];
  /** Ids of the columns to show, in any order (table order follows COLUMNS). */
  columns: string[];
  sort: Sort;
  onSort: (key: SortKey) => void;
  onOpen: (slug: string) => void;
  /** Optional row checkboxes, e.g. to pick startups to compare. */
  selection?: { selected: string[]; max: number; onToggle: (slug: string) => void };
};

/** Startups as rows; columns chosen by the caller, sortable from their headers. */
export function StartupTable({ startups, columns, sort, onSort, onOpen, selection }: Props) {
  const visible = COLUMNS.filter((c) => c.locked || columns.includes(c.id));

  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>
            {selection && <th aria-label="Select for comparison" />}
            {visible.map((c) => (
              <HeaderCell key={c.id} column={c} sort={sort} onSort={onSort} />
            ))}
          </tr>
        </thead>
        <tbody>
          {startups.map((s) => (
            <tr key={s.slug} className="clickable" onClick={() => onOpen(s.slug)}>
              {selection && (
                <td onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    aria-label={`Compare ${s.name}`}
                    checked={selection.selected.includes(s.slug)}
                    disabled={!selection.selected.includes(s.slug) && selection.selected.length >= selection.max}
                    onChange={() => selection.onToggle(s.slug)}
                  />
                </td>
              )}
              {visible.map((c) => (
                <td key={c.id} className={cn(c.numeric && "num", c.cellClassName)}>
                  {c.cell(s)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HeaderCell({ column, sort, onSort }: { column: Column; sort: Sort; onSort: (key: SortKey) => void }) {
  const key = column.sortKey;
  if (!key) return <th className={cn(column.numeric && "num")}>{column.header}</th>;

  const active = sort.key === key;
  const Icon = !active ? ChevronsUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;

  return (
    <th
      className={cn(column.numeric && "num")}
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
    >
      <button
        type="button"
        onClick={() => onSort(key)}
        // Keep the header's uppercase look; form controls reset text-transform.
        className={cn(
          "group inline-flex cursor-pointer items-center gap-1 uppercase hover:text-foreground",
          active && "text-foreground",
        )}
      >
        {column.header}
        <Icon
          aria-hidden
          className={cn(
            "size-3.5",
            active
              ? "text-primary"
              : "opacity-0 transition-opacity group-hover:opacity-60 group-focus-visible:opacity-60",
          )}
        />
      </button>
    </th>
  );
}
