import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { Button } from "../ui/button";
import type { StartupSummary } from "../../api/types";
import type { SearchSort, SearchSortKey } from "../../lib/discover-search";
import { COLUMNS } from "./columns";

export function StartupTable({
  startups,
  columns,
  sort,
  onSort,
  onOpen,
}: {
  startups: StartupSummary[];
  columns: string[];
  sort: SearchSort;
  onSort: (key: SearchSortKey) => void;
  onOpen: (slug: string) => void;
}) {
  const visible = COLUMNS.filter((c) => c.locked || columns.includes(c.id));
  return (
    <div className="table-wrap">
      <table className="data" aria-label="Startup search results">
        <thead>
          <tr>
            {visible.map((c) => (
              <th
                key={c.id}
                className={c.numeric ? "num" : undefined}
                aria-sort={
                  sort.key === c.sortKey
                    ? sort.direction === "asc"
                      ? "ascending"
                      : "descending"
                    : undefined
                }
              >
                {c.sortKey ? (
                  <Button variant="ghost" size="sm" onClick={() => c.sortKey && onSort(c.sortKey)}>
                    {c.header}
                    {sort.key === c.sortKey ? (
                      sort.direction === "asc" ? (
                        <ArrowUp />
                      ) : (
                        <ArrowDown />
                      )
                    ) : (
                      <ArrowUpDown />
                    )}
                  </Button>
                ) : (
                  c.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {startups.map((s) => (
            <tr key={s.slug} className="clickable" onClick={() => onOpen(s.slug)}>
              {visible.map((c) => (
                <td key={c.id} className={`${c.cellClassName ?? ""} ${c.numeric ? "num" : ""}`}>
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
