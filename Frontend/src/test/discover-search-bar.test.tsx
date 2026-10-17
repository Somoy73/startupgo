import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DiscoverSearchBar } from "@/components/DiscoverSearchBar";
import { emptyFilters } from "@/lib/discover-search";

const base = { filters: emptyFilters(), busy: false, onSearch: () => {}, onFiltersChange: () => {}, onClear: () => {} };

describe("Search bar", () => {
  it("submits the trimmed query", () => {
    const onSearch = vi.fn();
    render(<DiscoverSearchBar query="" {...base} onSearch={onSearch} />);
    fireEvent.change(screen.getByLabelText("Search text"), { target: { value: "  kelp  " } });
    fireEvent.click(screen.getByRole("button", { name: "AI Search" }));
    expect(onSearch).toHaveBeenCalledWith("kelp");
  });

  it("offers example searches until there is a query", () => {
    const onSearch = vi.fn();
    const { rerender } = render(<DiscoverSearchBar query="" {...base} onSearch={onSearch} />);
    fireEvent.click(screen.getByRole("button", { name: "seaweed packaging" }));
    expect(onSearch).toHaveBeenCalledWith("seaweed packaging");
    rerender(<DiscoverSearchBar query="kelp" {...base} onSearch={onSearch} />);
    expect(screen.queryByRole("button", { name: "seaweed packaging" })).not.toBeInTheDocument();
  });

  it("shows set filters as chips that remove themselves", () => {
    const onFiltersChange = vi.fn();
    render(<DiscoverSearchBar query="" {...base} filters={{ ...emptyFilters(), countries: ["Namibia"] }} onFiltersChange={onFiltersChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove filter Namibia" }));
    expect(onFiltersChange).toHaveBeenCalledWith(emptyFilters());
  });

  it("no longer offers the EU Projects switch", () => {
    render(<DiscoverSearchBar query="" {...base} />);
    expect(screen.queryByRole("button", { name: "EU Projects" })).not.toBeInTheDocument();
  });
});
