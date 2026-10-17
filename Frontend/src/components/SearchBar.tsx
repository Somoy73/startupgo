import { Search } from "lucide-react";
import type { SearchFilters } from "../lib/search";
export function SearchBar({
  query,
  onQueryChange,
}: {
  query: string;
  filters: SearchFilters;
  onQueryChange: (v: string) => void;
}) {
  return (
    <div className="search-bar">
      <Search />
      <input
        aria-label="Search startups"
        placeholder='Try "seaweed finland" or "carbon capture"'
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
      />
    </div>
  );
}
