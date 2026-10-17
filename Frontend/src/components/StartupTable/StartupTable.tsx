import { LuArrowDown, LuArrowUp, LuChevronsUpDown } from "react-icons/lu";
import type { StartupSummary } from "@/api/types";
import type { Sort, SortKey } from "@/lib/sort";
import { COLUMNS, type Column } from "./columns";
import { cx, num, table, td, th } from "@/components/ui";

interface Props {
  startups: StartupSummary[];
  /** Ids of the columns to show, in any order (table order follows COLUMNS). */
  columns: string[];
  sort: Sort;
  onSort: (key: SortKey) => void;
  onOpen: (slug: string) => void;
  /** Optional row checkboxes, e.g. to pick startups to compare. */
  selection?: { selected: string[]; max: number; onToggle: (slug: string) => void };
}

const CARD_CELL = "max-md:border-0 max-md:p-0";
const CARD_LABEL =
  "max-md:before:block max-md:before:text-2xs max-md:before:text-muted max-md:before:content-[attr(data-label)]";

/** Startups as rows; columns chosen by the caller, sortable from their headers. */
export function StartupTable({ startups, columns, sort, onSort, onOpen, selection }: Props) {
  const visible = COLUMNS.filter((c) => c.locked || columns.includes(c.id));

  return (
    <div className="overflow-x-auto">
      <table className={table}>
        {/* Phones: rows become two-column cards, labelled from data-label. */}
        <thead className="max-md:hidden">
          <tr>
            {selection && <th aria-label="Select for comparison" />}
            {visible.map((c) => (
              <HeaderCell key={c.id} column={c} sort={sort} onSort={onSort} />
            ))}
          </tr>
        </thead>
        <tbody>
          {startups.map((s) => (
            <tr
              key={s.slug}
              className="cursor-pointer hover:bg-surface-2 max-md:grid max-md:grid-cols-2 max-md:gap-x-3 max-md:gap-y-1.5 max-md:border-b max-md:border-grid max-md:px-1 max-md:py-3.5"
              onClick={() => onOpen(s.slug)}
            >
              {selection && (
                <td className={cx(td, CARD_CELL)} onClick={(e) => e.stopPropagation()}>
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
                <td
                  key={c.id}
                  className={cx(
                    td,
                    CARD_CELL,
                    c.full ? "max-md:col-span-full" : CARD_LABEL,
                    c.numeric && cx(num, "max-md:text-left"),
                    c.cellClassName,
                  )}
                  data-label={c.full ? undefined : c.header}
                >
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
  if (!column.sortKey) return <th className={cx(th, column.numeric && num)}>{column.header}</th>;

  const active = sort.key === column.sortKey;
  const Icon = !active ? LuChevronsUpDown : sort.dir === "asc" ? LuArrowUp : LuArrowDown;
  const key = column.sortKey;

  return (
    <th
      className={cx(th, column.numeric && num)}
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
    >
      <button
        type="button"
        onClick={() => onSort(key)}
        // th's uppercase small-caps look; form controls reset text-transform and letter-spacing.
        className={cx(
          "group inline-flex cursor-pointer items-center gap-1 border-0 bg-transparent p-0 font-semibold tracking-[0.03em] uppercase hover:text-fg",
          active && "text-fg",
        )}
      >
        {column.header}
        <Icon
          size={13}
          className={
            active
              ? "text-accent"
              : "opacity-0 transition-opacity group-hover:opacity-60 group-focus-visible:opacity-60"
          }
        />
      </button>
    </th>
  );
}
